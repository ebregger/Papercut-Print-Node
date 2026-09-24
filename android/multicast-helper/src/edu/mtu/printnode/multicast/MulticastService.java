package edu.mtu.printnode.multicast;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.net.wifi.WifiManager;
import android.os.IBinder;

public class MulticastService extends Service {
    private WifiManager.MulticastLock lock;

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        NotificationManager manager = getSystemService(NotificationManager.class);
        manager.createNotificationChannel(new NotificationChannel(
            "discovery", "Printer discovery", NotificationManager.IMPORTANCE_LOW));
        PendingIntent launch = PendingIntent.getActivity(this, 0,
            new Intent(this, MainActivity.class), PendingIntent.FLAG_IMMUTABLE);
        Notification notification = new Notification.Builder(this, "discovery")
            .setSmallIcon(android.R.drawable.ic_menu_share)
            .setContentTitle("PaperCut printer discovery")
            .setContentText("Listening for local printer searches")
            .setContentIntent(launch)
            .build();
        startForeground(1, notification);
        if (lock == null) {
            WifiManager wifi = getSystemService(WifiManager.class);
            lock = wifi.createMulticastLock("papercut-printer-discovery");
            lock.setReferenceCounted(false);
            lock.acquire();
        }
        return START_STICKY;
    }

    @Override public void onDestroy() {
        if (lock != null && lock.isHeld()) lock.release();
        super.onDestroy();
    }

    @Override public IBinder onBind(Intent intent) { return null; }
}
