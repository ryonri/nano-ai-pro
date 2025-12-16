import streamlit as st
import google.generativeai as genai
from io import BytesIO
import zipfile
import concurrent.futures
import time
import json
import os

# --- 設定 & 定数 ---
st.set_page_config(page_title="Gemini NanoBananaPro", layout="wide", page_icon="🍌")
BATCH_SIZE = 30  # 本番時の生成枚数

# スタイル定義
st.markdown("""
<style>
    .main-title {font-size: 3em; color: #4285F4; text-align: center; font-weight: bold;}
    .sub-title {text-align: center; color: #555;}
    .stButton>button {width: 100%; font-weight: bold;}
    /* テストボタンの色（緑） */
    div[data-testid="column"]:nth-of-type(1) .stButton>button {background-color: #34A853; color: white;}
    /* 本番ボタンの色（青） */
    div[data-testid="column"]:nth-of-type(2) .stButton>button {background-color: #4285F4; color: white;}
</style>
""", unsafe_allow_html=True)

# --- タイトル ---
st.markdown('<div class="main-title">🍌 Gemini NanoBananaPro 🍌</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Google最強AI搭載・サムネ一括生成ツール (Safety Edition)</div>', unsafe_allow_html=True)
st.markdown("---")

# --- サイドバー設定 ---
with st.sidebar:
    st.header("⚙️ Settings (Google)")
    api_key = st.text_input("Google API Key", type="password")
    st.caption("※ Google AI Studioで取得したキーを入力してください")
    
    style_preset = st.selectbox("Style Preset", [
        "YouTubeサムネイル風 (高コントラスト・文字スペースあり)",
        "フォトリアル・ビジネス",
        "アニメ・イラスト調",
        "3Dレンダー・モダン",
        "指定なし"
    ])
    st.info("💡 まずは「テスト生成」で1枚だけ試して、課金設定や動作を確認することをお勧めします。")

# --- メインエリア ---
col1, col2 = st.columns([2, 1])

with col1:
    topic = st.text_area("サムネイルのテーマ・キーワード (例: 『初心者向けAI副業』)", height=100)

with col2:
    st.write("### 操作パネル")
    st.write(f"🍌 エンジン: **Gemini & Imagen 3**")
    st.write("👇 どちらかを選択してください")
    
    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        test_btn = st.button("🧪 テスト生成 (1枚確認用)")
    with btn_col2:
        batch_btn = st.button(f"🚀 限界突破生成 ({BATCH_SIZE}枚一括)")

# --- 関数定義 ---

def generate_prompts_gemini(topic, style, count):
    """Gemini 1.5 Flashを使ってプロンプトを考案"""
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"""
    YouTubeサムネイルのプロフェッショナルとして、画像生成AI（Imagen 3）用の英語プロンプトを{count}個作成してください。
    テーマ: {topic}, スタイル: {style}
    条件: 16:9の構図、文字を入れる余白を確保。出力は純粋なJSONリスト形式のみ(例: ["prompt1", "prompt2"])。
    """
    try:
        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        prompts = json.loads(response.text)
        if isinstance(prompts, list): return prompts[:count]
        elif isinstance(prompts, dict): return list(prompts.values())[0][:count]
        else: return []
    except: return []

def generate_image_imagen(prompt_text):
    """Imagen 3を使って画像を生成"""
    try:
        model = genai.GenerativeModel('imagen-3.0-generate-001')
        result = model.generate_images(
            prompt=prompt_text + ", aspect ratio 16:9, high quality thumbnail, text free space",
            number_of_images=1, aspect_ratio="16:9", safety_filter_threshold="BLOCK_ONLY_HIGH",
        )
        if result.images: return result.images[0].image_bytes
        else: return None
    except: return None

# --- 実行ロジック ---
if api_key and topic:
    genai.configure(api_key=api_key)
    
    # === テスト生成モード (1枚) ===
    if test_btn:
        st.divider()
        st.write("### 🧪 テスト生成結果 (1枚)")
        with st.spinner("🧠 Geminiが構図を考案中..."):
            prompts = generate_prompts_gemini(topic, style_preset, 1)
        
        if prompts:
            with st.spinner("🎨 Imagenが画像を描画中..."):
                img_bytes = generate_image_imagen(prompts[0])
            
            if img_bytes:
                st.image(img_bytes, caption="テスト生成画像 (16:9)", use_column_width=True)
                st.success("🎉 テスト生成成功！問題なければ「限界突破生成」へ進んでください。")
            else:
                st.error("画像の生成に失敗しました。APIキーの権限(Imagen使用可否)や課金設定を確認してください。")
        else:
             st.error("プロンプト生成に失敗しました。テーマを変えて試してください。")

    # === 本番一括生成モード (30枚) ===
    elif batch_btn:
        st.divider()
        status_text = st.empty()
        progress_bar = st.progress(0)
        
        status_text.write("🧠 Geminiが30パターンの構図を考案中...")
        prompts = generate_prompts_gemini(topic, style_preset, BATCH_SIZE)
        
        if prompts:
            st.write(f"✅ プロンプト完成。Imagenで30枚の並列生成を開始します...")
            images_data = []
            completed_count = 0
            
            # 並列処理 (同時実行数3)
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                future_to_prompt = {executor.submit(generate_image_imagen, p): p for p in prompts}
                for future in concurrent.futures.as_completed(future_to_prompt):
                    try:
                        img_bytes = future.result()
                        if img_bytes: images_data.append(img_bytes)
                    except: pass
                    completed_count += 1
                    progress_bar.progress(completed_count / BATCH_SIZE)
                    status_text.write(f"🎨 生成中... ({completed_count}/{BATCH_SIZE}枚完了)")
                    time.sleep(1)

            if images_data:
                zip_buffer = BytesIO()
                with zipfile.ZipFile(zip_buffer, "w") as zf:
                    for i, img in enumerate(images_data):
                        zf.writestr(f"gemini_thumb_{i+1:03d}.jpg", img)
                
                st.success(f"🎉 限界突破完了！ {len(images_data)}枚のサムネイルを生成しました！")
                st.download_button(label="📦 画像をZIPでダウンロード", data=zip_buffer.getvalue(), file_name="nanobanana_pro_images.zip", mime="application/zip")
                st.write("### プレビュー (一部)")
                cols = st.columns(4)
                for i, col in enumerate(cols):
                    if i < len(images_data): col.image(images_data[i], caption=f"Image {i+1}", use_column_width=True)
            else:
                st.error("1枚も生成できませんでした。APIキーの設定を確認してください。")

elif (test_btn or batch_btn) and not api_key:
    st.warning("⚠️ Google API Keyを入力してください。")
