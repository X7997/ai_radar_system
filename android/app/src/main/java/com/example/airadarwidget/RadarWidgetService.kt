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
            val urlStr = "https://gist.githubusercontent.com/X7997/816a07bc292aaf7d9936c4e4f8d3f5d8/raw/ai_radar_events.json" 
            
            val url = URL(urlStr)
            val connection = url.openConnection() as HttpURLConnection
            connection.requestMethod = "GET"
            
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
                                summary = event.optString("summary"),
                                url = event.optString("url"),
                                tag = event.optString("tag")
                            )
                        )
                    }
                }
            } else {
                // Mock data if URL fails
                items.add(RadarItem("No Data", "Check URL", "", "Error"))
            }
        } catch (e: Exception) {
            e.printStackTrace()
            // Add a mock item for visual testing
            items.add(RadarItem("Local Mock Event", "AI Radar Widget setup incomplete. Update Gist URL.", "https://codexradar.com", "System"))
        }
    }

    override fun onDestroy() {
        items.clear()
    }

    override fun getCount(): Int = items.size

    override fun getViewAt(position: Int): RemoteViews {
        if (position >= items.size) return RemoteViews(context.packageName, R.layout.widget_item)
        
        val item = items[position]
        val views = RemoteViews(context.packageName, R.layout.widget_item)
        
        // Populate UI
        views.setTextViewText(R.id.item_title, item.title)
        views.setTextViewText(R.id.item_summary, item.summary)
        
        val timeStr = SimpleDateFormat("MM-dd HH:mm", Locale.getDefault()).format(Date())
        views.setTextViewText(R.id.item_time, "$timeStr, [${item.tag}]")

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
    val summary: String,
    val url: String,
    val tag: String
)
