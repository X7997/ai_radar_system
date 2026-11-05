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
            // 设置启动 RemoteViewsService 的 Intent，为集合视图提供数据源
            val intent = Intent(context, RadarWidgetService::class.java).apply {
                // 将 App Widget ID 附加到 Intent 参数中
                putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, appWidgetId)
                data = Uri.parse(toUri(Intent.URI_INTENT_SCHEME))
            }

            // 实例化小组件布局的 RemoteViews 对象
            val views = RemoteViews(context.packageName, R.layout.widget_layout).apply {
                // 配置 RemoteViews 适配器以连接 RemoteViewsService 服务
                setRemoteAdapter(R.id.widget_list_view, intent)
                setEmptyView(R.id.widget_list_view, R.id.empty_view)
                
                // 绑定当前更新时间
                val sdf = java.text.SimpleDateFormat("yyyy-MM-dd HH:mm", java.util.Locale.getDefault())
                val currentDate = sdf.format(java.util.Date())
                setTextViewText(R.id.widget_date, currentDate)
            }

            // 列表项点击跳转模板（适配 Android 14+ / API 34+ 显式 Intent 契约）
            val clickIntentTemplate = Intent(context, MainActivity::class.java)
            val clickPendingIntentTemplate: PendingIntent = PendingIntent.getActivity(
                context, 0, clickIntentTemplate,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE
            )
            views.setPendingIntentTemplate(R.id.widget_list_view, clickPendingIntentTemplate)

            // 通知 AppWidgetManager 更新小组件视图与列表数据
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
