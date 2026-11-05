package com.example.airadarwidget

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.widget.RemoteViews
import android.widget.RemoteViewsService
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class RadarWidgetService : RemoteViewsService() {
    override fun onGetViewFactory(intent: Intent): RemoteViewsFactory {
        return RadarRemoteViewsFactory(this.applicationContext, intent)
    }
}

class RadarRemoteViewsFactory(
    private val context: Context,
    intent: Intent
) : RemoteViewsService.RemoteViewsFactory {

    private val items: MutableList<RadarItem> = mutableListOf()

    override fun onCreate() {}

    override fun onDataSetChanged() {
        // Fetch JSON from the Gist URL.
        // This is called when the widget is created or updated. It runs in a background thread.
        items.clear()
        try {
            val baseUrl = "https://gist.githubusercontent.com/X7997/7ad36328320740c54905a64368c2ee2f/raw/ai_radar_events.json" 
            val urlStr = "$baseUrl?t=${System.currentTimeMillis()}"
            val url = URL(urlStr)
            val connection = url.openConnection() as HttpURLConnection
            connection.requestMethod = "GET"
            connection.connectTimeout = 5000
            connection.readTimeout = 5000
            
            if (connection.responseCode == HttpURLConnection.HTTP_OK) {
                val response = connection.inputStream.bufferedReader().readText()
                val jsonObject = JSONObject(response)
                val eventsArray = jsonObject.optJSONArray("events")
                
                if (eventsArray != null) {
                    for (i in 0 until eventsArray.length()) {
                        val event = eventsArray.getJSONObject(i)
                        items.add(
                            RadarItem(
                                title = event.optString("title"),
                                enDesc = event.optString("en_desc", event.optString("summary")),
                                zhDesc = event.optString("zh_desc"),
                                url = event.optString("url"),
                                tag = event.optString("tag")
                            )
                        )
                    }
                }
            } else {
                // 网络异常或无数据时的优雅回退提示
                items.add(RadarItem("暂无最新早报数据", "请检查网络连接或 Gist 数据源。", "", "", "系统提示"))
            }
        } catch (e: Exception) {
            e.printStackTrace()
            // 发生异常时的容灾演示提示
            items.add(RadarItem("AI Radar 桌面小组件已就绪", "正在等待清晨 07:15 智脑节点自动推送...", "", "https://codexradar.com", "状态正常"))
        }
    }

    override fun onDestroy() {
        items.clear()
    }

    override fun getCount(): Int = items.size

    private fun formatMarkdown(text: String): String {
        if (text.isEmpty()) return ""
        val boldPattern = Regex("\\*\\*(.*?)\\*\\*")
        // Render bold keywords in tech blue (#1976D2) for sharp contrast on black text
        return boldPattern.replace(text, "<font color='#1976D2'><b>$1</b></font>")
    }

    private fun parseHtml(htmlStr: String): CharSequence {
        return if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.N) {
            android.text.Html.fromHtml(htmlStr, android.text.Html.FROM_HTML_MODE_COMPACT)
        } else {
            android.text.Html.fromHtml(htmlStr)
        }
    }

    private fun formatTag(tag: String, title: String): String {
        var t = tag.trim()
        if (t.startsWith("#")) t = t.substring(1).trim()
        if (t.startsWith("【#") && t.endsWith("】")) t = t.substring(2, t.length - 1).trim()
        if (t.startsWith("【") && t.endsWith("】")) t = t.substring(1, t.length - 1).trim()
        
        if (t.isEmpty()) {
            t = when {
                title.contains("Codex") || title.contains("Tibo") -> "Codex 独家雷达"
                title.contains("外交") || title.contains("出口管制") || title.contains("中美") || title.contains("政策") -> "宏观与科技政策"
                title.contains("芯片") || title.contains("半导体") || title.contains("NVIDIA") -> "芯片与算力前沿"
                title.contains("具身智能") || title.contains("机器人") -> "具身智能与机器人"
                title.contains("Agent") || title.contains("模型") || title.contains("Claude") -> "前沿模型与 Agent"
                title.contains("开源") || title.contains("GitHub") -> "开源与极客生态"
                else -> "全球 AI 产业精选"
            }
        }
        return if (t.startsWith("·")) t else "· $t"
    }

    override fun getViewAt(position: Int): RemoteViews {
        if (position >= items.size) return RemoteViews(context.packageName, R.layout.widget_item)
        
        val item = items[position]
        val views = RemoteViews(context.packageName, R.layout.widget_item)
        
        // Row 1: Source / Category Tag (Above title, formatted like Douyin cards)
        val displayTag = formatTag(item.tag, item.title)
        if (displayTag.isNotEmpty()) {
            views.setViewVisibility(R.id.item_tag, android.view.View.VISIBLE)
            views.setTextViewText(R.id.item_tag, displayTag)
        } else {
            views.setViewVisibility(R.id.item_tag, android.view.View.GONE)
        }

        // Row 2: Title (Full width with bold parsing)
        views.setTextViewText(R.id.item_title, parseHtml(formatMarkdown(item.title)))
        
        // Row 3: Primary Description (Render Markdown **bold** as true Bold Spans)
        views.setTextViewText(R.id.item_en_desc, parseHtml(formatMarkdown(item.enDesc)))
        
        if (item.zhDesc.isNotEmpty()) {
            views.setViewVisibility(R.id.item_zh_desc, android.view.View.VISIBLE)
            views.setTextViewText(R.id.item_zh_desc, parseHtml(formatMarkdown(item.zhDesc)))
        } else {
            views.setViewVisibility(R.id.item_zh_desc, android.view.View.GONE)
        }

        // Fill in the intent template to open the URL
        val fillInIntent = Intent().apply {
            data = Uri.parse(item.url.takeIf { it.isNotEmpty() } ?: "https://codexradar.com")
        }
        views.setOnClickFillInIntent(R.id.item_container, fillInIntent)

        return views
    }

    override fun getLoadingView(): RemoteViews? = null
    override fun getViewTypeCount(): Int = 1
    override fun getItemId(position: Int): Long = position.toLong()
    override fun hasStableIds(): Boolean = true
}

data class RadarItem(
    val title: String,
    val enDesc: String,
    val zhDesc: String,
    val url: String,
    val tag: String
)
