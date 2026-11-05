package com.example.airadarwidget

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.widget.RemoteViews

class RadarWidgetProvider : AppWidgetProvider() {

    override fun onUpdate(
        context: Context,
        appWidgetManager: AppWidgetManager,
        appWidgetIds: IntArray
    ) {
        for (appWidgetId in appWidgetIds) {
            updateAppWidget(context, appWidgetManager, appWidgetId)
        }
    }
    
    companion object {
        fun updateAppWidget(
            context: Context,
            appWidgetManager: AppWidgetManager,
            appWidgetId: Int
        ) {
            // Set up the intent that starts the RemoteViewsService, which will
            // provide the views for this collection.
            val intent = Intent(context, RadarWidgetService::class.java).apply {
                // Add the app widget ID to the intent extras.
                putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, appWidgetId)
                data = Uri.parse(toUri(Intent.URI_INTENT_SCHEME))
            }

            // Instantiate the RemoteViews object for the app widget layout.
            val views = RemoteViews(context.packageName, R.layout.widget_layout).apply {
                // Set up the RemoteViews object to use a RemoteViews adapter.
                // This adapter connects to a RemoteViewsService through the specified intent.
                setRemoteAdapter(R.id.widget_list_view, intent)
                setEmptyView(R.id.widget_list_view, R.id.empty_view)
                
                // Set current date
                val sdf = java.text.SimpleDateFormat("yyyy-MM-dd HH:mm", java.util.Locale.getDefault())
                val currentDate = sdf.format(java.util.Date())
                setTextViewText(R.id.widget_date, currentDate)
            }

            // Template for item click to open browser (API 34+ fix: use explicit intent)
            val clickIntentTemplate = Intent(context, MainActivity::class.java)
            val clickPendingIntentTemplate: PendingIntent = PendingIntent.getActivity(
                context, 0, clickIntentTemplate,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE
            )
            views.setPendingIntentTemplate(R.id.widget_list_view, clickPendingIntentTemplate)

            // Instruct the widget manager to update the widget
            appWidgetManager.updateAppWidget(appWidgetId, views)
            appWidgetManager.notifyAppWidgetViewDataChanged(appWidgetId, R.id.widget_list_view)
        }
    }

    override fun onReceive(context: Context, intent: Intent) {
        super.onReceive(context, intent)
        if (intent.action == "com.example.airadarwidget.ACTION_ITEM_CLICK") {
            val url = intent.data
            if (url != null) {
                try {
                    val browserIntent = Intent(Intent.ACTION_VIEW, url).apply {
                        flags = Intent.FLAG_ACTIVITY_NEW_TASK
                    }
                    context.startActivity(browserIntent)
                } catch (e: Exception) {
                    e.printStackTrace()
                }
            }
        }
    }
}
