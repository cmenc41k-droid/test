package org.screenassistant.nativeparts;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.graphics.Bitmap;
import android.graphics.PixelFormat;
import android.hardware.display.DisplayManager;
import android.hardware.display.VirtualDisplay;
import android.media.Image;
import android.media.ImageReader;
import android.media.projection.MediaProjection;
import android.media.projection.MediaProjectionManager;
import android.os.Build;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.IBinder;
import android.util.DisplayMetrics;
import android.view.WindowManager;

import java.io.FileOutputStream;
import java.nio.ByteBuffer;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/**
 * Foreground-сервис (тип mediaProjection) + захват экрана.
 * Кадры сохраняются в JPEG только по запросу capture().
 */
public class CaptureService extends Service {
    public static final int IDLE = 0, PENDING = 1, READY = 2, DENIED = 3;
    public static volatile int state = IDLE;
    static int resultCode;
    static Intent resultData;
    private static volatile CaptureService instance;

    private static final String CHANNEL = "screen_assistant_capture";
    private static final int MAX_EDGE = 1920;

    private MediaProjection projection;
    private VirtualDisplay display;
    private ImageReader reader;
    private HandlerThread thread;
    private volatile Req pending;

    private static class Req {
        final String path;
        final CountDownLatch latch = new CountDownLatch(1);
        volatile boolean ok;
        Req(String p) { path = p; }
    }

    public static int getState() { return state; }

    public static void stopCapture(Context ctx) {
        ctx.stopService(new Intent(ctx, CaptureService.class));
    }

    /** Блокирующий вызов: сохраняет следующий кадр в JPEG. Вызывать НЕ из UI-потока. */
    public static boolean capture(String path, int timeoutMs) {
        CaptureService s = instance;
        if (s == null || state != READY) return false;
        Req r = new Req(path);
        s.pending = r;
        try {
            if (!r.latch.await(timeoutMs, TimeUnit.MILLISECONDS)) {
                s.pending = null;
                return false;
            }
        } catch (InterruptedException e) {
            return false;
        }
        return r.ok;
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        try {
            startAsForeground();
            if (resultData == null) throw new IllegalStateException("no projection data");
            MediaProjectionManager m =
                    (MediaProjectionManager) getSystemService(MEDIA_PROJECTION_SERVICE);
            projection = m.getMediaProjection(resultCode, resultData);
            resultData = null; // токен одноразовый

            thread = new HandlerThread("sa-capture");
            thread.start();
            Handler h = new Handler(thread.getLooper());
            projection.registerCallback(new MediaProjection.Callback() {
                @Override public void onStop() { stopSelf(); }
            }, h);

            DisplayMetrics dm = new DisplayMetrics();
            ((WindowManager) getSystemService(WINDOW_SERVICE)).getDefaultDisplay().getRealMetrics(dm);
            reader = ImageReader.newInstance(dm.widthPixels, dm.heightPixels, PixelFormat.RGBA_8888, 2);
            display = projection.createVirtualDisplay("ScreenAssistant", dm.widthPixels, dm.heightPixels,
                    dm.densityDpi, DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
                    reader.getSurface(), null, h);
            reader.setOnImageAvailableListener(new ImageReader.OnImageAvailableListener() {
                @Override public void onImageAvailable(ImageReader r) { onFrame(r); }
            }, h);
            instance = this;
            state = READY;
        } catch (Throwable t) {
            state = DENIED;
            stopSelf();
        }
        return START_NOT_STICKY;
    }

    private void startAsForeground() {
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        Notification.Builder b;
        if (Build.VERSION.SDK_INT >= 26) {
            nm.createNotificationChannel(new NotificationChannel(CHANNEL, "Screen Assistant",
                    NotificationManager.IMPORTANCE_LOW));
            b = new Notification.Builder(this, CHANNEL);
        } else {
            b = new Notification.Builder(this);
        }
        Notification n = b.setContentTitle("Screen Assistant")
                .setContentText("Плавающий режим активен")
                .setSmallIcon(getApplicationInfo().icon)
                .setOngoing(true).build();
        if (Build.VERSION.SDK_INT >= 29) {
            startForeground(1, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION);
        } else {
            startForeground(1, n);
        }
    }

    private void onFrame(ImageReader r) {
        Image img = null;
        try {
            img = r.acquireLatestImage();
            if (img == null) return;
            Req req = pending;
            if (req == null) return;
            pending = null;
            try {
                Image.Plane p = img.getPlanes()[0];
                ByteBuffer buf = p.getBuffer();
                int ps = p.getPixelStride(), rs = p.getRowStride();
                int w = img.getWidth(), hgt = img.getHeight();
                Bitmap full = Bitmap.createBitmap(rs / ps, hgt, Bitmap.Config.ARGB_8888);
                full.copyPixelsFromBuffer(buf);
                Bitmap bmp = Bitmap.createBitmap(full, 0, 0, w, hgt);
                int big = Math.max(w, hgt);
                if (big > MAX_EDGE) {
                    float k = (float) MAX_EDGE / big;
                    bmp = Bitmap.createScaledBitmap(bmp, Math.round(w * k), Math.round(hgt * k), true);
                }
                FileOutputStream fo = new FileOutputStream(req.path);
                bmp.compress(Bitmap.CompressFormat.JPEG, 90, fo);
                fo.close();
                req.ok = true;
            } catch (Throwable t) {
                req.ok = false;
            }
            req.latch.countDown();
        } catch (Throwable ignored) {
        } finally {
            if (img != null) img.close();
        }
    }

    @Override
    public void onDestroy() {
        instance = null;
        Req r = pending;
        if (r != null) r.latch.countDown();
        try { if (reader != null) reader.setOnImageAvailableListener(null, null); } catch (Throwable ignored) {}
        try { if (display != null) display.release(); } catch (Throwable ignored) {}
        try { if (reader != null) reader.close(); } catch (Throwable ignored) {}
        try { if (projection != null) projection.stop(); } catch (Throwable ignored) {}
        if (thread != null) thread.quitSafely();
        if (state != DENIED) state = IDLE;
        super.onDestroy();
    }

    @Override public IBinder onBind(Intent i) { return null; }
}
