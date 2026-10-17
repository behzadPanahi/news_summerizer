import streamlit as st
import feedparser
import requests
import json
import os
import re
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
from time import mktime

CONFIG_FILE = "config.json"

st.set_page_config(
    page_title="سامانه پایش هوشمند اخبار بین‌الملل",
    page_icon="🌍",
    layout="wide"
)

# استایل راست‌چین (RTL) و فونت وزیر
st.markdown("""
<style>
    @import url('https://v1.fontapi.ir/css/Vazir');
    * {
        font-family: 'Vazir', sans-serif !important;
    }
    .main {
        direction: rtl;
        text-align: right;
    }
    .stTabs [data-baseweb="tab-list"] {
        direction: rtl;
    }
    .stMarkdown, .stText, p, div, span, h1, h2, h3, h4, h5, h6 {
        direction: rtl;
        text-align: right;
    }
    .report-box {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        border-right: 5px solid #0d6efd;
        border-radius: 8px;
        padding: 18px;
        margin-bottom: 20px;
        color: #212529;
    }
</style>
""", unsafe_allow_html=True)


def load_config():
    default_config = {
        "api_key": "",
        "base_url": "https://api.gapgpt.app/v1",
        "model_name": "gpt-4o-mini",
        "sources": []
    }
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default_config, f, ensure_ascii=False, indent=2)
        return default_config
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data
    except Exception:
        return default_config


def save_config(config_data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config_data, f, ensure_ascii=False, indent=2)


def clean_html(raw_html):
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    text = soup.get_text(separator=" ")
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def parse_entry_time(entry):
    for attr in ["published_parsed", "updated_parsed", "created_parsed"]:
        t_struct = getattr(entry, attr, None)
        if t_struct:
            try:
                return datetime.fromtimestamp(mktime(t_struct), timezone.utc)
            except Exception:
                pass
    return None


def fetch_recent_news(rss_url, hours=24, max_items=25):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        }
        resp = requests.get(rss_url.strip(), headers=headers, timeout=12)
        resp.encoding = 'utf-8'
        
        feed = feedparser.parse(resp.content)
        if not feed.entries:
            return []
            
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        items = []

        for entry in feed.entries:
            entry_time = parse_entry_time(entry)
            if entry_time is None or entry_time >= cutoff:
                title = clean_html(getattr(entry, "title", ""))
                summary = clean_html(getattr(entry, "summary", "")) or clean_html(getattr(entry, "description", ""))
                if title:
                    items.append({
                        "title": title,
                        "summary": summary[:300]
                    })
            if len(items) >= max_items:
                break
                
        if not items and feed.entries:
            for entry in feed.entries[:max_items]:
                title = clean_html(getattr(entry, "title", ""))
                summary = clean_html(getattr(entry, "summary", "")) or clean_html(getattr(entry, "description", ""))
                if title:
                    items.append({"title": title, "summary": summary[:300]})

        return items
    except Exception as err:
        st.warning(f"خطا در دریافت فید ({rss_url}): {err}")
        return []


def call_ai_chat(prompt, config):
    api_key = config.get("api_key", "").strip()
    base_url = config.get("base_url", "https://api.gapgpt.app/v1").rstrip("/")
    model_name = config.get("model_name", "gpt-4o-mini").strip()

    if not api_key:
        return "⚠️ کلید API هوش مصنوعی در تنظیمات وارد نشده است."

    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "system",
                "content": (
                    "شما یک تحلیل‌گر ارشد روابط بین‌الملل و مانیتورینگ رسانه‌ای هستید. "
                    "وظیفه شما بررسی اخبار انگلیسی خبرگزاری‌های جهان و ارائه خروجی‌های ساختاریافته، "
                    "دقیق، بدون جانب‌داری و به زبان فارسی کاملاً روان و شسته و رفته است."
                )
            },
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.5
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=90)
        if response.status_code == 200:
            res_json = response.json()
            return res_json["choices"][0]["message"]["content"].strip()
        else:
            return f"❌ خطای API هوش مصنوعی ({response.status_code}): {response.text}"
    except Exception as e:
        return f"❌ خطا در برقراری ارتباط با مدل هوش مصنوعی: {str(e)}"


config = load_config()

st.title("🌍 سامانه رصد و تحلیل هوشمند خبرگزاری‌های بین‌المللی")
st.caption("پایش اخبار رسانه‌های برتر جهان با خلاصه‌سازی و تحلیل تطبیقی هوش مصنوعی")

tabs = st.tabs(["📊 داشبورد و تحلیل اخبار", "📰 مدیریت خبرگزاری‌ها", "⚙️ تنظیمات هوش مصنوعی"])

with tabs[0]:
    sources = config.get("sources", [])
    if not sources:
        st.info("هیچ منبع خبری تعریف نشده است. لطفاً از تب «مدیریت خبرگزاری‌ها» منابع را اضافه کنید.")
    else:
        st.subheader("۱. انتخاب منابع جهت استخراج")
        
        source_names = [s.get("name", "منبع ناشناس") for s in sources]
        
        selected_sources = st.multiselect(
            "خبرگزاری‌های مورد نظر برای بررسی را انتخاب کنید:",
            options=source_names,
            default=source_names[:6]
        )
        
        st.divider()
        st.subheader("۲. تنظیمات و حالت تحلیل")
        
        analysis_mode = st.radio(
            "شیوه پردازش و تحلیل اخبار:",
            [
                "۱. خلاصه‌سازی تک‌به‌تک (خلاصه مجزا و موجز برای هر خبرگزاری)",
                "۲. گزارش جامع و تحلیلی تجمیعی (دیده‌بان کلان بازه انتخابی)",
                "۳. تحلیل مقایسه‌ای دو به دو (بررسی زاویه دید دو رسانه مختلف)"
            ]
        )

        cmp_source_1, cmp_source_2 = None, None
        if "۳. تحلیل مقایسه‌ای" in analysis_mode:
            c1, c2 = st.columns(2)
            with c1:
                cmp_source_1 = st.selectbox("خبرگزاری اول:", source_names, index=0)
            with c2:
                cmp_source_2 = st.selectbox("خبرگزاری دوم:", source_names, index=min(1, len(source_names)-1))

        col_hours, _ = st.columns([1, 2])
        with col_hours:
            hours_filter = st.number_input(
                "محدوده زمانی اخبار (ساعت گذشته):",
                min_value=1,
                max_value=168,
                value=24,
                step=1,
                help="اخبار منتشرشده در این تعداد ساعت گذشته استخراج و تحلیل خواهند شد."
            )
        
        if st.button("🚀 شروع استخراج و تحلیل اخبار", type="primary", use_container_width=True):
            target_list = []
            if "۳. تحلیل مقایسه‌ای" in analysis_mode:
                target_names = list(set([cmp_source_1, cmp_source_2]))
                target_list = [s for s in sources if s.get("name") in target_names]
            else:
                target_list = [s for s in sources if s.get("name") in selected_sources]

            if not target_list:
                st.warning("لطفاً حداقل یک خبرگزاری را انتخاب کنید.")
            else:
                news_data = {}
                progress_bar = st.progress(0)
                status_text = st.empty()

                for idx, src in enumerate(target_list):
                    name = src.get("name", "بدون نام")
                    url = src.get("rss_url") or src.get("url", "")
                    status_text.text(f"در حال واکشی آخرین اخبار از {name}...")
                    
                    items = fetch_recent_news(url, hours=hours_filter)
                    if items:
                        news_data[name] = items
                    progress_bar.progress((idx + 1) / len(target_list))

                status_text.text("استخراج به پایان رسید. در حال ارسال داده‌ها به هوش مصنوعی...")

                if not news_data:
                    st.error("هیچ خبری در بازه زمانی انتخابی یافت نشد.")
                else:
                    st.success(f"تعداد {len(news_data)} منبع با موفقیت واکشی شد.")

                    if "۱. خلاصه‌سازی تک‌به‌تک" in analysis_mode:
                        st.subheader("📑 خلاصه اخبار خبرگزاری‌ها (به تفکیک)")
                        for s_name, items in news_data.items():
                            news_text = "\n".join([f"- {it['title']}: {it['summary']}" for it in items[:15]])
                            prompt = f"""
بر اساس اخبار {hours_filter} ساعت گذشته خبرگزاری «{s_name}»، یک خلاصه جامع، ساختاریافته و در قالب یک یا دو پاراگراف روان به زبان فارسی ارائه دهید.
تمرکز اصلی بر رویدادهای محوری و اولویت‌های پوشش خبری این رسانه باشد.

لیست عناوین و اخبار واکشی‌شده:
{news_text}
"""
                            with st.spinner(f"در حال نگارش خلاصه فارسی برای {s_name}..."):
                                summary_res = call_ai_chat(prompt, config)
                            
                            with st.expander(f"📌 {s_name} ({len(items)} خبر دریافت شد)", expanded=True):
                                st.markdown(f"<div class='report-box'>{summary_res}</div>", unsafe_allow_html=True)

                    elif "۲. گزارش جامع و تحلیلی تجمیعی" in analysis_mode:
                        st.subheader("🌐 دیده‌بان کلان فضای رسانه‌ای جهان")
                        all_news_text = ""
                        for s_name, items in news_data.items():
                            all_news_text += f"\n\n### خبرگزاری: {s_name}\n"
                            all_news_text += "\n".join([f"- {it['title']}: {it['summary']}" for it in items[:10]])

                        prompt = f"""
شما دسترسی به اخبار مهم‌ترین خبرگزاری‌های بین‌المللی در {hours_filter} ساعت گذشته دارید:
{all_news_text}

لطفاً یک گزارش راهبردی جامع به زبان فارسی شامل بخش‌های زیر تولید کنید:
۱. **مهم‌ترین سرخط‌ها و ترندهای مشترک بین‌المللی** (چه موضوعاتی در صدر اخبار جهان قرار داشتند؟)
۲. **تفکیک حوزه‌ای تحولات کلیدی** (سیاسی/ژئوپلیتیک، اقتصادی، فناوری/محیط‌زیست)
۳. **جمع‌بندی تحلیلی از جریان غالب خبری در رسانه‌های بین‌المللی**
"""
                        with st.spinner("در حال تحلیل کلان و تولید گزارش جامع..."):
                            overall_res = call_ai_chat(prompt, config)
                        st.markdown(f"<div class='report-box'>{overall_res}</div>", unsafe_allow_html=True)

                    elif "۳. تحلیل مقایسه‌ای" in analysis_mode:
                        st.subheader(f"⚖️ تحلیل مقایسه‌ای: {cmp_source_1} در برابر {cmp_source_2}")
                        items1 = news_data.get(cmp_source_1, [])
                        items2 = news_data.get(cmp_source_2, [])

                        text1 = "\n".join([f"- {it['title']}: {it['summary']}" for it in items1[:12]])
                        text2 = "\n".join([f"- {it['title']}: {it['summary']}" for it in items2[:12]])

                        prompt = f"""
دو منبع خبری «{cmp_source_1}» و «{cmp_source_2}» را بر اساس اخبار {hours_filter} ساعت گذشته‌شان مقایسه کنید:

اخبار {cmp_source_1}:
{text1}

اخبار {cmp_source_2}:
{text2}

لطفاً به زبان فارسی و در قالبی شفاف موارد زیر را مقایسه کنید:
۱. **تفاوت در اولویت‌بندی سوژه‌ها:** هر رسانه کدام موضوع را تیتر اصلی خود قرار داده است؟
۲. **زاویه دید و چارچوب‌بندی (Framing):** آیا لحن، رویکرد سیاسی یا تمرکز جغرافیایی متفاوتی وجود دارد؟
۳. **نتیجه‌گیری تحلیلی.**
"""
                        with st.spinner("در حال انجام تحلیل تطبیقی هوشمند..."):
                            cmp_res = call_ai_chat(prompt, config)
                        st.markdown(f"<div class='report-box'>{cmp_res}</div>", unsafe_allow_html=True)

with tabs[1]:
    st.subheader("مدیریت و ویرایش منابع خبری")
    
    current_sources = config.get("sources", [])

    with st.expander("➕ افزودن خبرگزاری جدید", expanded=False):
        new_name = st.text_input("نام رسانه:")
        new_rss = st.text_input("آدرس فید RSS:")
        if st.button("ثبت خبرگزاری"):
            if new_name and new_rss:
                new_id = max([s.get("id", idx) for idx, s in enumerate(current_sources)] + [0]) + 1
                current_sources.append({
                    "id": new_id,
                    "name": new_name.strip(),
                    "rss_url": new_rss.strip()
                })
                config["sources"] = current_sources
                save_config(config)
                st.success(f"منبع «{new_name}» با موفقیت افزوده شد.")
                st.rerun()
            else:
                st.error("لطفاً نام و آدرس فید را تکمیل کنید.")

    st.write(f"تعداد منابع فعال: **{len(current_sources)}**")
    
    for idx, s in enumerate(current_sources):
        s_id = s.get("id", idx + 1)
        s_name = s.get("name", f"منبع شماره {idx+1}")
        s_url = s.get("rss_url") or s.get("url", "")

        with st.expander(f"📰 {s_name}", expanded=False):
            c_name, c_url = st.columns([1, 2])
            edit_name = c_name.text_input("نام", value=s_name, key=f"name_{s_id}_{idx}")
            edit_url = c_url.text_input("آدرس RSS", value=s_url, key=f"url_{s_id}_{idx}")

            b_save, b_del = st.columns([1, 1])
            if b_save.button("💾 ذخیره تغییرات", key=f"save_{s_id}_{idx}"):
                s["name"] = edit_name.strip()
                s["rss_url"] = edit_url.strip()
                config["sources"] = current_sources
                save_config(config)
                st.success("تغییرات ذخیره شد.")
                st.rerun()

            if b_del.button("🗑️ حذف این منبع", key=f"del_{s_id}_{idx}"):
                current_sources = [item for i, item in enumerate(current_sources) if i != idx]
                config["sources"] = current_sources
                save_config(config)
                st.warning("منبع حذف شد.")
                st.rerun()

with tabs[2]:
    st.subheader("تنظیمات اتصال به هوش مصنوعی (API)")
    
    cfg_api_key = st.text_input("کلید اختصاصی API (API Key):", value=config.get("api_key", ""), type="password")
    cfg_base_url = st.text_input("آدرس پایه (Base URL):", value=config.get("base_url", "https://api.gapgpt.app/v1"))
    cfg_model = st.text_input("نام مدل (Model Name):", value=config.get("model_name", "gpt-4o-mini"))

    if st.button("ذخیره تنظیمات هوش مصنوعی", type="primary"):
        config["api_key"] = cfg_api_key.strip()
        config["base_url"] = cfg_base_url.strip()
        config["model_name"] = cfg_model.strip()
        save_config(config)
        st.success("تنظیمات با موفقیت در config.json ذخیره شدند.")
