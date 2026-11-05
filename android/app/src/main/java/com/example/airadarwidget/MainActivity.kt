package com.example.airadarwidget

import android.app.Activity
import android.os.Bundle
import android.widget.TextView
import android.widget.ScrollView
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import kotlin.concurrent.thread

class MainActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        val url = intent?.data
        if (url != null && url.toString().startsWith("http")) {
            try {
                val browserIntent = android.content.Intent(android.content.Intent.ACTION_VIEW, url)
                startActivity(browserIntent)
            } catch (e: Exception) {
                // Ignore if no browser
            }
            finish()
            return
        }
        
        val textView = TextView(this)
        textView.text = "正在连接 AI Radar 数据中枢..."
        textView.setPadding(32, 32, 32, 32)
        
        val scrollView = ScrollView(this)
        scrollView.addView(textView)
        setContentView(scrollView)
        
        thread {
            try {
                val baseUrl = "https://gist.githubusercontent.com/X7997/7ad36328320740c54905a64368c2ee2f/raw/ai_radar_events.json" 
                val urlStr = "$baseUrl?t=${System.currentTimeMillis()}"
                val connectionUrl = URL(urlStr)
                val connection = connectionUrl.openConnection() as HttpURLConnection
                connection.requestMethod = "GET"
                connection.connectTimeout = 5000
                connection.readTimeout = 5000
                
                if (connection.responseCode == HttpURLConnection.HTTP_OK) {
                    val response = connection.inputStream.bufferedReader().readText()
                    runOnUiThread { textView.text = "今日早报数据已同步成功：\n\n$response" }
                } else {
                    runOnUiThread { textView.text = "网络连接异常 HTTP ${connection.responseCode}" }
                }
            } catch (e: Exception) {
                runOnUiThread { textView.text = "数据获取异常：${e.message}\n\n${e.stackTraceToString()}" }
            }
        }
    }
}
