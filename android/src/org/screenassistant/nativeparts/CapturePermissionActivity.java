package org.screenassistant.nativeparts;

import android.app.Activity;
import android.content.Intent;
import android.media.projection.MediaProjectionManager;
import android.os.Build;
import android.os.Bundle;

/** Прозрачная Activity: показывает системный диалог MediaProjection и запускает CaptureService. */
public class CapturePermissionActivity extends Activity {
    private static final int REQ = 7001;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        CaptureService.state = CaptureService.PENDING;
        MediaProjectionManager m =
                (MediaProjectionManager) getSystemService(MEDIA_PROJECTION_SERVICE);
        startActivityForResult(m.createScreenCaptureIntent(), REQ);
    }

    @Override
    protected void onActivityResult(int req, int res, Intent data) {
        super.onActivityResult(req, res, data);
        if (req == REQ && res == RESULT_OK && data != null) {
            CaptureService.resultCode = res;
            CaptureService.resultData = data;
            Intent s = new Intent(this, CaptureService.class);
            if (Build.VERSION.SDK_INT >= 26) startForegroundService(s); else startService(s);
        } else {
            CaptureService.state = CaptureService.DENIED;
        }
        finish();
    }
}
