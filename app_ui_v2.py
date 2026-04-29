import os
import io
import re
import json
import base64
import random
import tempfile
import hashlib
import uuid
from typing import Dict, Any, Optional, List, Tuple
from textwrap import dedent

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
from streamlit_mic_recorder import mic_recorder
from gtts import gTTS

# =========================
# 1. 基础配置
# =========================
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key) if api_key else None

st.set_page_config(
    page_title="乐龄伴",
    page_icon="💙",
    layout="wide"
)

# =========================
# 2. 初始化状态
# =========================
DEFAULT_GREETING = "您好，我是乐龄伴。您慢慢说，我会一步一步陪您看。"

if "messages" not in st.session_state:
    st.session_state.messages = []

if "today_greeting" not in st.session_state:
    greetings = [
        "今天您先别着急，有事我们慢慢说。",
        "有不明白的地方，您直接问我，我一条一条跟您说。",
        "要办事也没关系，我们一步一步来，不用一下记太多。",
        "您有想问的事，就直接说，我陪您慢慢理清楚。"
    ]
    st.session_state.today_greeting = random.choice(greetings)

if "last_voice_sig" not in st.session_state:
    st.session_state.last_voice_sig = ""

if "voice_processing" not in st.session_state:
    st.session_state.voice_processing = False

if "autoplay_audio_b64" not in st.session_state:
    st.session_state.autoplay_audio_b64 = ""

if "autoplay_audio_id" not in st.session_state:
    st.session_state.autoplay_audio_id = ""

if "autoplay_pending" not in st.session_state:
    st.session_state.autoplay_pending = False

if "last_reply_text" not in st.session_state:
    st.session_state.last_reply_text = ""

if "current_topic" not in st.session_state:
    st.session_state.current_topic = ""

if "current_scene" not in st.session_state:
    st.session_state.current_scene = ""

if "current_intent" not in st.session_state:
    st.session_state.current_intent = ""

if "current_city" not in st.session_state:
    st.session_state.current_city = ""

if "current_district" not in st.session_state:
    st.session_state.current_district = ""

if "current_province" not in st.session_state:
    st.session_state.current_province = ""

if "font_size_mode" not in st.session_state:
    st.session_state.font_size_mode = "大字"

if "voice_enabled" not in st.session_state:
    st.session_state.voice_enabled = True

if "send_trigger" not in st.session_state:
    st.session_state.send_trigger = 0

if "input_counter" not in st.session_state:
    st.session_state.input_counter = 0

if "audio_paused" not in st.session_state:
    st.session_state.audio_paused = False

if "audio_command" not in st.session_state:
    st.session_state.audio_command = ""

if "current_audio_dom_id" not in st.session_state:
    st.session_state.current_audio_dom_id = ""

if "service_progress" not in st.session_state:
    st.session_state.service_progress = {
        "category": "",
        "service_item": "",
        "city": "",
        "district": "",
        "current_stage": ""
    }

if not st.session_state.messages:
    st.session_state.messages.append({
        "id": str(uuid.uuid4()),
        "role": "assistant",
        "content": DEFAULT_GREETING,
        "audio_b64": ""
    })

# =========================
# 3. 简体中文统一处理
# =========================
def to_simplified(text: str) -> str:
    if not text:
        return text

    phrase_map = {
        "謝謝": "谢谢", "請問": "请问", "這裡": "这里", "這個": "这个", "醫保": "医保",
        "辦理": "办理", "查詢": "查询", "聯繫": "联系", "幫助": "帮助", "資訊": "信息",
        "電話": "电话", "醫院": "医院", "醫療": "医疗", "服務": "服务", "熱線": "热线",
        "戶口本": "户口本", "證件": "证件", "身份證": "身份证", "簡單": "简单", "沒有": "没有",
        "嗎": "吗", "現在": "现在", "會": "会", "還有": "还有", "問題": "问题",
        "準備": "准备", "語音": "语音", "播放": "播放", "領取": "领取", "複雜": "复杂",
        "說明": "说明", "實際": "实际", "幾樣": "几样", "穩妥": "稳妥", "鬆": "松",
        "開門": "开门", "關門": "关门"
    }

    char_map = {
        "謝": "谢", "請": "请", "這": "这", "裡": "里", "個": "个", "醫": "医",
        "辦": "办", "詢": "询", "聯": "联", "繫": "系", "幫": "帮", "資": "资",
        "訊": "讯", "電": "电", "話": "话", "療": "疗", "務": "务", "熱": "热",
        "線": "线", "戶": "户", "證": "证", "簡": "简", "沒": "没", "嗎": "吗",
        "現": "现", "會": "会", "還": "还", "問": "问", "準": "准", "備": "备",
        "語": "语", "說": "说", "領": "领", "複": "复", "雜": "杂", "實": "实",
        "際": "际", "點": "点", "車": "车", "門": "门", "關": "关", "開": "开",
        "轉": "转", "騙": "骗", "號": "号", "機": "机", "讓": "让", "聽": "听",
        "幾": "几", "樣": "样", "穩": "稳"
    }

    for trad, simp in phrase_map.items():
        text = text.replace(trad, simp)

    text = "".join(char_map.get(ch, ch) for ch in text)
    return text.strip()

# =========================
# 4. 页面字号配置
# =========================
def get_font_sizes():
    mode = st.session_state.font_size_mode
    if mode == "标准字":
        return {"base": 18, "sidebar": 18, "button": 18, "input": 18}
    if mode == "超大字":
        return {"base": 24, "sidebar": 22, "button": 22, "input": 22}
    return {"base": 20, "sidebar": 19, "button": 20, "input": 20}

font_cfg = get_font_sizes()

# =========================
# 5. 新版页面样式
# =========================
st.markdown(f"""
<style>
html, body, [class*="css"] {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
                 "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
    font-size: {font_cfg["base"]}px !important;
}}

.stApp {{
    background: #F7F8FB !important;
}}

/* 关键：把主内容整体往下放，不要再压标题 */
.block-container {{
    padding-top: 4.2rem !important;
    padding-bottom: 2rem !important;
    max-width: 1450px;
}}

/* 顶部默认栏保留，但弱化 */
header[data-testid="stHeader"] {{
    background: rgba(255,255,255,0.92) !important;
    backdrop-filter: blur(2px);
}}

div[data-testid="stSidebar"] {{
    background: transparent !important;
}}

.left-panel {{
    background: #EEF1F7;
    border-radius: 22px;
    padding: 26px 22px 28px 22px;
    min-height: 82vh;
    overflow: visible !important;
}}

.brand-title {{
    font-size: 34px;
    font-weight: 800;
    color: #1F2937;
    margin-bottom: 14px;
    line-height: 1.35;
    white-space: nowrap;
}}

.brand-desc {{
    font-size: {font_cfg["sidebar"]}px;
    line-height: 1.9;
    color: #4B5563;
    margin-bottom: 22px;
}}

.hero-wrap {{
    margin-top: 0.8rem;
    margin-bottom: 28px;
}}

.hero-title {{
    font-size: 50px;
    font-weight: 800;
    color: #1F2937;
    margin-bottom: 12px;
    line-height: 1.25;
}}

.hero-subtitle {{
    font-size: 26px;
    font-weight: 700;
    color: #2563EB;
    margin-bottom: 14px;
}}

.hero-desc {{
    font-size: 20px;
    color: #4B5563;
    line-height: 1.9;
    margin-bottom: 10px;
}}

.hero-guide {{
    font-size: 19px;
    color: #2563EB;
    font-weight: 600;
}}

.notice-banner {{
    background: #DBEAFE;
    color: #1D4ED8;
    border-radius: 18px;
    padding: 16px 18px;
    font-size: 18px;
    font-weight: 700;
    margin-top: 14px;
    margin-bottom: 26px;
}}

.section-title {{
    font-size: 32px;
    font-weight: 800;
    color: #1F2937;
    margin-bottom: 18px;
}}

.custom-divider {{
    border-top: 1px solid #E5E7EB;
    margin-top: 26px;
    margin-bottom: 26px;
}}

.chat-card {{
    background: #FFFFFF;
    border-radius: 22px;
    padding: 24px;
    box-shadow: 0 6px 18px rgba(17, 24, 39, 0.05);
    margin-top: 12px;
}}

.assistant-bubble {{
    background: #FFFFFF;
    border: 1px solid #ECEFF5;
    border-radius: 16px;
    padding: 18px 20px;
    font-size: {font_cfg["base"]}px;
    color: #1F2937;
    line-height: 1.9;
    margin-bottom: 14px;
}}

.user-bubble {{
    background: #F8FAFC;
    border: 1px solid #E5E7EB;
    border-radius: 16px;
    padding: 16px 18px;
    font-size: {font_cfg["base"]}px;
    color: #374151;
    line-height: 1.8;
    margin-bottom: 14px;
}}

.answer-tag {{
    display: inline-block;
    background: #EFF6FF;
    color: #1D4ED8;
    border-radius: 999px;
    padding: 6px 12px;
    font-size: 14px;
    font-weight: 700;
    margin-top: 6px;
    margin-bottom: 12px;
}}

.answer-title {{
    font-size: 30px;
    font-weight: 800;
    color: #1F2937;
    margin-bottom: 18px;
}}

.step-row {{
    display: flex;
    align-items: flex-start;
    gap: 14px;
    margin-bottom: 14px;
}}

.step-num {{
    width: 36px;
    height: 36px;
    border-radius: 10px;
    background: #3B82F6;
    color: white;
    font-size: 18px;
    font-weight: 800;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}}

.step-text {{
    font-size: {font_cfg["base"] + 1}px;
    color: #374151;
    line-height: 1.8;
    font-weight: 600;
    margin-top: -2px;
}}

.tip-box {{
    background: #FFF7ED;
    border: 1px solid #FDBA74;
    border-radius: 14px;
    padding: 14px 16px;
    margin-top: 18px;
    font-size: {font_cfg["base"] - 1}px;
    color: #9A3412;
    line-height: 1.7;
    font-weight: 600;
}}

.input-wrap {{
    margin-top: 24px;
}}

/* 不再强行把普通按钮拉得特别大，改成更接近录音按钮的尺寸 */
div.stButton > button {{
    width: 100%;
    min-height: 44px;
    height: 44px;
    border-radius: 12px !important;
    font-size: 15px !important;
    font-weight: 700 !important;
    border: 1px solid #D6DCE5 !important;
    background: #FFFFFF !important;
    color: #1F2937 !important;
    box-shadow: none !important;
    padding: 0 10px !important;
}}

div.stButton > button:hover {{
    border-color: #9FB7E9 !important;
    color: #1D4ED8 !important;
}}

div[data-testid="stTextInput"] {{
    background: transparent !important;
}}

div[data-testid="stTextInput"] > div {{
    background: transparent !important;
}}

div[data-testid="stTextInput"] > div > div {{
    background: #FFFFFF !important;
    border: 1px solid #D9DDE5 !important;
    border-radius: 16px !important;
    box-shadow: none !important;
}}

div[data-testid="stTextInput"] input {{
    min-height: 56px !important;
    font-size: {font_cfg["input"]}px !important;
    border-radius: 16px !important;
    background: #FFFFFF !important;
    color: #111111 !important;
    border: none !important;
    box-shadow: none !important;
    -webkit-text-fill-color: #111111 !important;
}}

div[data-testid="stTextInput"] input::placeholder {{
    color: #666666 !important;
    opacity: 1 !important;
    -webkit-text-fill-color: #666666 !important;
}}

div[data-baseweb="radio"] label {{
    font-size: {font_cfg["sidebar"]}px !important;
}}

audio {{
    width: 100%;
    margin-top: 8px;
    margin-bottom: 6px;
    background: #FFFFFF !important;
    border-radius: 14px !important;
}}
</style>
""", unsafe_allow_html=True)

# =========================
# 6. 知识库读取
# =========================
CATEGORY_ALIASES = {
    "医疗健康": ["医保", "医疗", "医院", "看病", "门诊", "住院", "慢病", "报销", "异地就医", "医保卡", "特殊病种"],
    "社保与退休": ["社保", "社保卡", "人社", "退休", "退休金", "养老金", "资格认证", "养老保险", "社保转移", "灵活就业"],
    "老年补贴与福利": ["高龄津贴", "老人补贴", "老年补贴", "低保", "困难补助", "残疾人补贴", "居家养老", "养老服务申请"],
    "政务服务": ["身份证补办", "户口迁移", "居住证", "婚姻登记", "派出所", "户口本", "身份证"],
    "金融与日常服务": ["银行卡", "银行卡补办", "银行卡冻结", "自动扣费", "手机支付", "养老金到账", "银行"],
    "社区与居家服务": ["社区服务中心", "居委会", "街道办", "上门养老服务", "居家护理", "老年大学", "社区活动"],
    "出行与生活服务": ["公交卡", "地铁优惠卡", "出行预约", "医院接送", "打车", "出行"],
    "反诈与风险防范": ["反诈", "诈骗", "骗子", "验证码诈骗", "社保停缴短信", "冒充医保局", "投资理财骗局", "转账", "陌生电话"],
    "数字生活辅助": ["微信", "小程序", "扫码", "扫一扫", "验证码在哪", "验证码收不到", "线上预约", "网上预约", "登录不上"]
}

TERM_EXPLAINERS = {
    "异地就医备案": "异地就医备案，简单说，就是您去外地看病前，先在医保系统里做个登记。这样有些地方就能直接按医保结算。",
    "门诊统筹": "门诊统筹，简单说，就是平时看门诊，有些费用也可能按规定报销，不是只有住院才能用医保。",
    "养老待遇资格认证": "养老待遇资格认证，简单说，就是定期确认您本人还符合领取养老金条件。",
    "社保关系转移": "社保关系转移，简单说，就是把原来参保地的社保接到新的地方去，缴费年限一般能接着算。",
    "灵活就业参保": "灵活就业参保，简单说，就是没有固定单位代缴社保的人，自己按规定参保。"
}

def load_policy_knowledge() -> Dict[str, Any]:
    try:
        with open("policy_knowledge.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def get_scene_entries(policy_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    entries = []
    for category_name, category_data in policy_data.items():
        if not isinstance(category_data, dict):
            continue
        common_questions = category_data.get("常见问题", {})
        if isinstance(common_questions, dict):
            for scene_name, scene_data in common_questions.items():
                if not isinstance(scene_data, dict):
                    continue
                aliases = scene_data.get("aliases", [])
                if not isinstance(aliases, list):
                    aliases = []
                entries.append({
                    "category": category_name,
                    "scene_name": scene_name,
                    "aliases": aliases,
                    "data": scene_data
                })
    return entries

def get_scene_data(scene_name: str, policy_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    for entry in get_scene_entries(policy_data):
        if entry["scene_name"] == scene_name:
            return entry
    return None

def get_category_data(category_name: str, policy_data: Dict[str, Any]) -> Dict[str, Any]:
    return policy_data.get(category_name, {})

def scene_belongs_to_category(scene_name: str, policy_data: Dict[str, Any]) -> str:
    entry = get_scene_data(scene_name, policy_data)
    return entry["category"] if entry else ""

def build_policy_context(category_name: str, scene_name: str, policy_data: Dict[str, Any]) -> str:
    category_data = get_category_data(category_name, policy_data)
    scene_entry = get_scene_data(scene_name, policy_data) if scene_name else None
    context = {
        "category_name": category_name,
        "category_data": category_data,
        "scene_name": scene_name,
        "scene_data": scene_entry["data"] if scene_entry else {}
    }
    return json.dumps(context, ensure_ascii=False, indent=2)

# =========================
# 7. 最近上下文
# =========================
def build_recent_history(max_turns: int = 8) -> List[Dict[str, str]]:
    history = []
    recent_messages = st.session_state.messages[-max_turns:]
    for msg in recent_messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role in ["user", "assistant"] and content:
            history.append({"role": role, "content": content})
    return history

# =========================
# 8. 识别话题、场景、地区
# =========================
def detect_category_from_text(user_text: str, policy_data: Dict[str, Any]) -> str:
    text = to_simplified(user_text)

    for category_name in policy_data.keys():
        if category_name in text:
            return category_name

    for category_name, aliases in CATEGORY_ALIASES.items():
        if any(alias in text for alias in aliases) and category_name in policy_data:
            return category_name

    return ""

def detect_scene_from_kb(user_text: str, policy_data: Dict[str, Any]) -> str:
    text = to_simplified(user_text)

    for entry in get_scene_entries(policy_data):
        if entry["scene_name"] and entry["scene_name"] in text:
            return entry["scene_name"]

    for entry in get_scene_entries(policy_data):
        aliases = entry.get("aliases", [])
        if any(alias in text for alias in aliases):
            return entry["scene_name"]

    return ""

def update_current_topic(user_text: str, policy_data: Dict[str, Any]):
    category = detect_category_from_text(user_text, policy_data)
    if category:
        st.session_state.current_topic = category

def update_current_scene(user_text: str, policy_data: Dict[str, Any]):
    scene = detect_scene_from_kb(user_text, policy_data)
    if scene:
        st.session_state.current_scene = scene

def update_location_state(user_text: str):
    text = to_simplified(user_text)

    province_keywords = [
        "北京", "天津", "上海", "重庆", "河北", "山西", "辽宁", "吉林", "黑龙江",
        "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南",
        "广东", "海南", "四川", "贵州", "云南", "陕西", "甘肃", "青海",
        "台湾", "内蒙古", "广西", "西藏", "宁夏", "新疆", "香港", "澳门"
    ]

    city_keywords = [
        "北京", "上海", "广州", "深圳", "杭州", "成都", "重庆", "武汉", "南京", "西安",
        "苏州", "天津", "长沙", "郑州", "青岛", "宁波", "东莞", "佛山", "厦门", "福州",
        "合肥", "昆明", "南宁", "济南", "沈阳", "大连", "哈尔滨", "长春"
    ]

    district_patterns = [
        r"[\u4e00-\u9fa5]{1,8}区",
        r"[\u4e00-\u9fa5]{1,8}县",
        r"[\u4e00-\u9fa5]{1,8}新区"
    ]

    for p in province_keywords:
        if p in text:
            st.session_state.current_province = p

    for city in city_keywords:
        if city in text:
            st.session_state.current_city = city

    for pattern in district_patterns:
        matches = re.findall(pattern, text)
        if matches:
            st.session_state.current_district = matches[-1]

# =========================
# 9. 意图识别
# =========================
def detect_followup_intent(user_text: str) -> str:
    text = to_simplified(user_text)

    if any(k in text for k in ["带什么", "材料", "原件", "复印件", "代办", "本人去", "准备什么"]):
        return "materials"
    if any(k in text for k in ["哪里办", "去哪办", "地址", "窗口", "网点", "大厅", "在哪里"]):
        return "location"
    if any(k in text for k in ["怎么办", "怎么弄", "步骤", "流程", "下一步"]):
        return "steps"
    if any(k in text for k in ["注意什么", "要注意", "提醒", "风险", "官方核实", "会不会白跑", "白跑"]):
        return "notes"

    return "general"

def is_public_service_category(category_name: str) -> bool:
    return category_name in [
        "医疗健康",
        "社保与退休",
        "老年补贴与福利",
        "政务服务",
        "金融与日常服务",
        "社区与居家服务",
        "出行与生活服务",
        "反诈与风险防范"
    ]

# =========================
# 10. 老人引导回复核心
# =========================
def detect_user_feeling(text: str) -> str:
    text = to_simplified(text)
    if any(k in text for k in ["怕白跑", "白跑", "跑一趟", "折腾", "麻烦", "来回", "坐地铁", "转三趟"]):
        return "怕白跑"
    if any(k in text for k in ["看不懂", "听不懂", "不明白", "不知道", "什么意思"]):
        return "看不懂"
    if any(k in text for k in ["记不住", "忘了", "一会就忘", "记不清"]):
        return "记不住"
    if any(k in text for k in ["不会用", "不会弄", "不会操作", "不会"]):
        return "不会操作"
    return ""

def get_dynamic_opening(user_text: str, category_name: str = "", scene_name: str = "", intent: str = "") -> str:
    text = to_simplified(user_text)
    feeling = detect_user_feeling(text)

    if feeling == "怕白跑":
        if scene_name in ["身份证补办", "居住证办理", "户口迁移", "退休办理"]:
            return "您担心白跑，这个想得很对，我们先把去之前要问清楚的事弄明白。"
        return "您担心白跑很正常，我先跟您说最要紧的一步。"

    if feeling == "看不懂":
        return "没关系，我不用难词，我直接用最简单的话跟您说。"

    if feeling == "记不住":
        return "没关系，您先记住最要紧的两三样就行。"

    if feeling == "不会操作":
        return "这个不用急，我带着您一小步一小步来。"

    if intent == "materials":
        return random.choice(["我先跟您说带什么。", "先把要带的东西弄清楚。", "咱们先看材料。"])
    if intent == "location":
        return random.choice(["我先跟您说去哪里更省事。", "先把去哪里办弄清楚。", "我先说地点。"])
    if intent == "steps":
        return random.choice(["这件事先做哪一步最重要，我直接跟您说。", "先把顺序理清楚就不容易乱。", "我先跟您说先做什么。"])
    if intent == "notes":
        return random.choice(["我先跟您说最容易出错的一点。", "先把最容易白跑的地方说清楚。", "我先提醒您最关键的一点。"])

    scene_openings = {
        "身份证补办": "补办身份证，先弄清楚能不能在当地办最重要。",
        "社保卡补办": "社保卡这件事，先别急，我先跟您说最先做哪一步。",
        "银行卡丢失或补办": "银行卡丢了，先保住卡里的钱最重要。",
        "银行卡冻结": "银行卡冻结，先别乱操作，我先帮您分清楚是什么情况。",
        "医保报销": "医保报销这件事，先把该留的材料弄清楚最重要。",
        "异地就医": "异地看病这件事，先看要不要备案最关键。",
        "退休办理": "退休这件事，我们先看第一步该问谁。",
        "养老金领取": "养老金这件事，我先跟您说钱一般怎么到手。",
        "资格认证": "这个认证听着麻烦，其实先弄清去哪做就行。",
        "高龄津贴": "高龄津贴这件事，先确认是不是能申请最重要。",
        "低保": "低保这件事，先看要准备哪类家庭情况材料。",
        "验证码收不到": "验证码收不到，先别反复点，我先带您查最常见的原因。",
        "验证码查看": "验证码这个事不难，我带您一步一步找。",
        "政务小程序": "找小程序这件事，最简单的办法就是先搜入口。",
        "线上预约": "预约这件事，我们先找入口，再看下一步。",
        "社保停缴短信": "这种短信先别信，我先跟您说怎么判断真假。",
        "冒充医保局": "这种电话先别急着照做，我先帮您判断风险。"
    }
    if scene_name in scene_openings:
        return scene_openings[scene_name]

    if category_name == "政务服务":
        return random.choice(["政务这类事，先把地点和材料弄清楚最重要。", "这类事先看在哪里办和带什么。", "政务问题，先把最关键的两步弄清楚。"])
    if category_name == "医疗健康":
        return random.choice(["看病和医保这类事，先分清您现在卡在哪一步。", "医疗这类事，先把最要紧的环节找出来。", "先别急，医疗这类问题一步一步看就行。"])
    if category_name == "社保与退休":
        return random.choice(["社保退休这类事，我先跟您说最先问什么。", "这类事先把顺序理清楚最重要。", "社保退休问题，先看最先做哪一步。"])
    if category_name == "金融与日常服务":
        return random.choice(["钱和卡这类事，先保安全最重要。", "这类事先别急着操作，先把最关键的一步抓住。", "钱和卡的问题，先处理最紧要的。"])
    if category_name == "反诈与风险防范":
        return random.choice(["这类事先别急着操作，我先帮您看真假。", "先别照着对方说的做，我们先判断风险。", "这类情况先核实最重要。"])
    if category_name == "数字生活辅助":
        return random.choice(["手机上的事不急，我先带您找第一步。", "这个先不用慌，咱们先找入口。", "数字操作这类事，一步一步来就行。"])

    return random.choice(["我先把最要紧的跟您说。", "这件事先抓住最关键的一步。", "咱们先把最重要的弄清楚。"])

def build_elder_opening(user_text: str = "", category_name: str = "", scene_name: str = "", intent: str = "", core_sentence: str = "") -> str:
    if any(k in core_sentence for k in ["别着急", "一步一步", "慢慢来", "最要紧"]):
        return ""
    return get_dynamic_opening(user_text, category_name, scene_name, intent)

def build_next_step_prompt(category_name: str, scene_name: str, intent: str = "") -> str:
    if intent == "materials":
        return random.choice(["后面我可以接着帮您看要不要本人去。", "接下来我也可以帮您看原件还是复印件。", "后面还可以继续帮您核对是不是能代办。"])
    if intent == "location":
        return random.choice(["后面我可以继续帮您缩小到更具体的办理地点。", "接下来也可以继续看先去哪个地方更方便。", "如果需要，我还能继续帮您看先问哪一边更省事。"])
    if intent == "steps":
        return random.choice(["后面我可以继续帮您往下排第二步。", "接下来我也可以继续跟您顺一下后面的步骤。", "如果您想，我还能继续把后面怎么做接着说下去。"])
    if intent == "notes":
        return random.choice(["后面我还可以继续提醒您哪一步最容易出错。", "接下来也可以继续帮您看怎么避免白跑。", "如果需要，我还能继续跟您说要注意的地方。"])

    default_prompts = {
        "身份证补办": ["后面我可以接着帮您看出门前先带哪两样最稳妥。", "接下来也可以继续跟您说先去哪里问。", "如果需要，我还能继续帮您看要不要先预约。"],
        "社保卡补办": ["后面我可以继续帮您看要不要先挂失。", "接下来也可以继续帮您看去银行还是去社保窗口。", "如果需要，我还能继续跟您核对补办材料。"],
        "退休办理": ["后面我可以继续帮您看先去问哪个窗口。", "接下来也可以继续把退休手续顺下去。", "如果需要，我还能继续跟您看要准备哪些材料。"],
        "养老金领取": ["后面我可以继续帮您看钱一般打到哪张卡。", "接下来也可以继续跟您说没到账时怎么办。", "如果需要，我还能继续帮您看去银行问还是去人社问。"],
        "资格认证": ["后面我可以继续帮您看是在手机上做还是去窗口做。", "接下来也可以继续帮您看认证时间怎么查。", "如果需要，我还能继续把认证步骤顺给您。"],
        "医保报销": ["后面我可以继续帮您看先留好哪几张票。", "接下来也可以继续帮您分门诊和住院。", "如果需要，我还能继续帮您顺一下报销流程。"],
        "异地就医": ["后面我可以继续帮您看去外地前要不要先备案。", "接下来也可以继续看回来以后怎么报销。", "如果需要，我还能继续帮您分清先做哪一步。"],
        "高龄津贴": ["后面我可以继续帮您看先去社区问还是去街道问。", "接下来也可以继续帮您看申请条件。", "如果需要，我还能继续帮您看一般要带什么。"],
        "银行卡丢失或补办": ["后面我可以继续帮您看去银行时要带什么。", "接下来也可以继续帮您看挂失以后怎么办。", "如果需要，我还能继续跟您看补卡那一步怎么问。"],
        "银行卡冻结": ["后面我可以继续帮您看先联系银行还是先去网点。", "接下来也可以继续帮您看这像不像诈骗。", "如果需要，我还能继续帮您分清是什么原因冻住的。"],
        "社保停缴短信": ["后面我可以继续帮您看这条短信先去哪里核实。", "接下来也可以继续帮您分真假短信怎么判断。", "如果需要，我还能继续帮您看先别做什么。"],
        "验证码收不到": ["后面我可以继续帮您看收不到短信时先检查哪里。", "接下来也可以继续帮您看是手机问题还是平台问题。", "如果需要，我还能继续帮您往下排查。"],
        "线上预约": ["后面我可以继续帮您看预约页面先点哪个按钮。", "接下来也可以继续帮您把预约顺序排一下。", "如果需要，我还能继续帮您看找不到入口时怎么办。"]
    }

    if scene_name in default_prompts:
        return random.choice(default_prompts[scene_name])

    if category_name == "政务服务":
        return random.choice(["后面我还可以继续帮您看材料。", "接下来也可以继续帮您看地点。", "如果需要，我还能继续顺一下流程。"])
    if category_name == "医疗健康":
        return random.choice(["后面我还可以继续帮您看材料。", "接下来也可以继续帮您分步骤。", "如果需要，我还能继续帮您看注意什么。"])
    if category_name == "社保与退休":
        return random.choice(["后面我还可以继续帮您看先问哪个窗口。", "接下来也可以继续帮您看材料。", "如果需要，我还能继续顺一下步骤。"])
    if category_name == "反诈与风险防范":
        return random.choice(["后面我还可以继续帮您看先找谁核实。", "接下来也可以继续帮您判断真假。", "如果需要，我还能继续跟您说先别做什么。"])
    if category_name == "数字生活辅助":
        return random.choice(["后面我还可以继续帮您看手机里先点哪里。", "接下来也可以继续把后面的操作顺给您。", "如果需要，我还能继续帮您一起找入口。"])

    return random.choice(["后面我还可以继续陪您往下看。", "接下来也可以继续把后面的事顺下去。", "如果需要，我还能继续帮您往下理。"])

def clean_lines_for_elder(lines: List[str], limit: int = 4) -> List[str]:
    out = []
    for line in lines:
        line = to_simplified(line).strip()
        if not line:
            continue
        line = line.replace("您先别着急，", "").replace("您别着急，", "")
        line = line.replace("咱们一步步来。", "").replace("咱们一步步来，", "").strip()
        if line and line not in out:
            out.append(line)
        if len(out) >= limit:
            break
    return out

def remove_repeated_comfort(text: str) -> str:
    patterns = ["您先别着急", "您别着急", "咱们一步步来", "我们一点一点来", "慢慢来"]
    seen = {p: False for p in patterns}
    lines = text.split("\n")
    cleaned_lines = []

    for line in lines:
        original = line
        for p in patterns:
            if p in line:
                if seen[p]:
                    line = line.replace(p, "").replace("，，", "，").strip(" ，。")
                else:
                    seen[p] = True
        if line.strip():
            cleaned_lines.append(line)
        elif original.strip() == "":
            cleaned_lines.append("")
    result = "\n".join(cleaned_lines)
    result = re.sub(r"\n{3,}", "\n\n", result)
    result = re.sub(r"，，+", "，", result)
    result = re.sub(r"。。+", "。", result)
    return result.strip()

def build_elder_guided_reply(
    user_text: str,
    core_sentence: str,
    steps: Optional[List[str]] = None,
    category_name: str = "",
    scene_name: str = "",
    intent: str = ""
) -> str:
    core_sentence = to_simplified(core_sentence).strip()
    opening = build_elder_opening(user_text=user_text, category_name=category_name, scene_name=scene_name, intent=intent, core_sentence=core_sentence)
    steps = clean_lines_for_elder(steps or [], limit=3)

    parts = []
    if opening:
        parts.append(opening)
    parts.append(core_sentence)
    if steps:
        parts.append("您先记住这几样就行：")
        for idx, step in enumerate(steps, start=1):
            parts.append(f"{idx}. {step}")
    parts.append(build_next_step_prompt(category_name, scene_name, intent))
    return remove_repeated_comfort("\n".join(parts)).strip()

def extract_short_points_from_text(text: str, limit: int = 3) -> Tuple[str, List[str]]:
    text = to_simplified(text).strip()
    if not text:
        return "我先把最要紧的跟您说。", []
    chunks = re.split(r"[。\n；;!！?？]+", text)
    chunks = [c.strip(" -•\t，,") for c in chunks if c.strip()]
    chunks = clean_lines_for_elder(chunks, limit=limit + 1)
    if not chunks:
        return "我先把最要紧的跟您说。", []
    return chunks[0], chunks[1:1 + limit]

def shorten_public_reply(text: str, user_text: str, category_name: str, scene_name: str, intent: str = "") -> str:
    core_sentence, steps = extract_short_points_from_text(text, limit=3)
    return build_elder_guided_reply(
        user_text=user_text,
        core_sentence=core_sentence,
        steps=steps,
        category_name=category_name,
        scene_name=scene_name,
        intent=intent
    )

# =========================
# 11. 模糊澄清、术语、数字、材料、高优先级场景
# =========================
def detect_vague_expression(user_input: str):
    text = to_simplified(user_input)
    vague_keywords = ["那个", "这个", "上次那个", "那个钱", "那个卡", "那个东西", "怎么弄", "不能用了", "找不到了", "不会弄", "不知道怎么搞"]
    return any(k in text for k in vague_keywords)

def explain_service_term(user_input: str) -> Tuple[str, str]:
    text = to_simplified(user_input)
    for term, explanation in TERM_EXPLAINERS.items():
        if term in text:
            return term, explanation
    return "", ""

def detect_term_explain_request(user_input: str):
    text = to_simplified(user_input)
    explain_keywords = ["什么意思", "是什么", "啥意思", "看不懂", "这个词是什么意思", "解释一下", "是啥"]
    return any(term in text for term in TERM_EXPLAINERS.keys()) or any(word in text for word in explain_keywords)

def detect_digital_help(user_input: str):
    text = to_simplified(user_input)
    keywords = [
        "验证码在哪", "验证码在哪里", "微信通知在哪", "微信消息在哪", "通知在哪",
        "小程序怎么进", "怎么进小程序", "怎么扫码", "扫一扫在哪",
        "怎么预约", "不会预约", "线上预约", "网上预约",
        "我不会线上办", "我不会网上办", "不会操作", "手机里找不到",
        "怎么看消息", "找不到小程序", "找不到入口", "不会用微信",
        "扫码失败", "登录不上", "验证码收不到"
    ]
    return any(k in text for k in keywords)

def answer_digital_help(user_input: str):
    text = to_simplified(user_input)

    if "验证码收不到" in text:
        return build_elder_guided_reply(user_input, "验证码收不到，先别反复点。", ["先看短信里有没有新消息", "确认手机号是不是填对了", "等一会儿再重新获取一次"], "数字生活辅助", "验证码收不到", "steps")
    if "验证码" in text:
        return build_elder_guided_reply(user_input, "验证码一般就在手机短信里。", ["先打开短信", "看最新那条消息", "里面那几位数字通常就是验证码"], "数字生活辅助", "验证码查看", "steps")
    if "登录不上" in text:
        return build_elder_guided_reply(user_input, "登录不上，先不要一直反复试。", ["先看看手机号是不是填对了", "再看看验证码或密码是不是对的", "最后再看看网络是不是正常"], "数字生活辅助", "登录不上", "steps")
    if "扫码失败" in text:
        return build_elder_guided_reply(user_input, "扫不出来时，先别急。", ["先看看二维码清不清楚", "再重新打开微信扫一扫", "把手机稍微挪近一点再试"], "数字生活辅助", "扫码失败", "steps")
    if "小程序" in text or "找不到入口" in text:
        return build_elder_guided_reply(user_input, "找小程序，最简单的办法就是在微信里搜。", ["先打开微信", "点上面的搜索框", "输入医保、社保或者政务服务去找"], "数字生活辅助", "政务小程序", "steps")
    if "预约" in text:
        return build_elder_guided_reply(user_input, "预约这件事，我们一点一点来。", ["先找到对应的小程序或公众号", "再找到您要办的事项", "最后选时间并提交"], "数字生活辅助", "线上预约", "steps")

    return build_elder_guided_reply(user_input, "这个操作我可以带着您慢慢来。", ["您先告诉我卡在哪一步", "我再只跟您说下一步", "不用一下记太多"], "数字生活辅助", "数字帮助", "steps")

def detect_material_check_need(user_input: str):
    text = to_simplified(user_input)
    keywords = ["带什么", "需要什么材料", "材料", "要准备什么", "准备什么", "原件还是复印件", "原件", "复印件", "能不能代办", "可以代办吗", "要不要本人去", "必须本人去吗", "本人去吗", "需要本人吗"]
    return any(k in text for k in keywords)

def build_material_check_reply(scene_name: str, user_input: str, policy_data: Dict[str, Any]):
    scene_entry = get_scene_data(scene_name, policy_data)
    if not scene_entry:
        return build_elder_guided_reply(user_input, "先别一下记太多，我先说最常用的几样。", ["先带身份证或户口本", "再带相关卡证", "有能证明身份的证件也顺手带上"], "", scene_name, "materials")

    scene_data = scene_entry["data"]
    materials = scene_data.get("常见材料", [])
    short_materials = clean_lines_for_elder(materials, limit=3)
    return build_elder_guided_reply(user_input, "先看材料。", short_materials if short_materials else ["身份证", "相关卡证", "能证明身份的材料"], scene_belongs_to_category(scene_name, policy_data), scene_name, "materials")

def answer_followup_detail(user_input: str, current_scene: str) -> str:
    text = to_simplified(user_input)
    if current_scene == "身份证补办":
        if "其他身份证明" in text or "什么意思" in text or "是什么" in text:
            return build_elder_guided_reply(user_input, "这里说的“其他身份证明材料”，就是除了户口本以外，能证明您是您本人的证件。", ["比如社保卡", "医保卡、居住证、驾驶证也算", "您手头有哪一样，就带哪一样"], "政务服务", current_scene, "materials")
        if "我在北京" in text or "能不能在北京补办" in text or "北京补办" in text or "广州补办" in text or "我在广州" in text:
            city = st.session_state.current_city or "当地"
            return build_elder_guided_reply(user_input, f"如果您现在住在{city}，很多情况下可以先在{city}问能不能异地补办身份证。", ["先别急着跑，最好先问清楚", "出门先带户口本", "再带社保卡或医保卡这类证件里的一样"], "政务服务", current_scene, "location")
        if "带什么" in text or "准备什么" in text:
            return build_elder_guided_reply(user_input, "我给您说最实在的。", ["先带户口本", "再带社保卡或医保卡", "有驾驶证、居住证也顺手带上"], "政务服务", current_scene, "materials")
    return ""

def answer_high_priority_finance_scene(user_input: str, scene_name: str) -> str:
    if scene_name == "银行卡丢失或补办":
        return build_elder_guided_reply(user_input, "银行卡丢了，最要紧的是先把这张卡挂失，别让别人动您的钱。", ["先马上打银行客服电话挂失", "再带身份证去银行网点补办新卡", "补办时顺便问清楚原来的钱是不是还在原账户里"], "金融与日常服务", scene_name, "steps")

    if scene_name == "银行卡冻结":
        return build_elder_guided_reply(user_input, "银行卡冻结了，先别乱操作，先弄清楚是密码输错、银行风控，还是别的原因。", ["先打银行官方客服电话问原因", "再按银行要求带身份证去网点处理", "不要相信陌生电话说可以帮您解冻"], "金融与日常服务", scene_name, "steps")
    return ""

# =========================
# 12. 公共服务辅助逻辑
# =========================
def need_city_for_public_service(user_text: str, category_name: str):
    text = to_simplified(user_text)
    if category_name in ["数字生活辅助"]:
        return False
    keywords = ["办理", "哪里办", "去哪办", "去哪", "地址", "窗口", "网点", "大厅", "中心", "在哪里领", "在哪里办", "去哪里领取", "去哪里办理"]
    return any(k in text for k in keywords)

def ask_for_exact_location_or_hours(user_text: str):
    text = to_simplified(user_text)
    keywords = ["具体位置", "具体地址", "地址在哪", "在哪里", "哪个大厅", "哪个窗口", "几点开门", "几点上班", "办公时间", "营业时间", "开门时间", "几点下班", "几点关门", "周末上班吗", "周六上班吗", "周日上班吗"]
    return any(k in text for k in keywords)

def has_precise_district():
    return bool(st.session_state.current_district)

def update_service_progress(category_name: str, scene_name: str):
    st.session_state.service_progress["category"] = category_name or ""
    st.session_state.service_progress["service_item"] = scene_name or ""
    st.session_state.service_progress["city"] = st.session_state.current_city or ""
    st.session_state.service_progress["district"] = st.session_state.current_district or ""
    if not scene_name:
        st.session_state.service_progress["current_stage"] = "clarify_service"
    elif not st.session_state.current_city and is_public_service_category(category_name):
        st.session_state.service_progress["current_stage"] = "clarify_location"
    else:
        st.session_state.service_progress["current_stage"] = "guide"

# =========================
# 13. 语音相关
# =========================
def clean_text_for_tts(text: str) -> str:
    text = to_simplified(text)
    text = re.sub(r"\*\*", "", text)
    text = re.sub(r"\*", "", text)
    text = re.sub(r"#+", "", text)
    text = re.sub(r"`+", "", text)
    text = re.sub(r"\[|\]|\(|\)", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def generate_tts_base64(text: str):
    if not st.session_state.voice_enabled:
        return ""
    try:
        text = clean_text_for_tts(text)
        tts = gTTS(text=text, lang="zh-CN")
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return base64.b64encode(fp.read()).decode("utf-8")
    except Exception:
        return ""

def set_latest_autoplay(audio_b64: str):
    if audio_b64:
        st.session_state.autoplay_audio_b64 = audio_b64
        st.session_state.autoplay_audio_id = str(uuid.uuid4())
        st.session_state.current_audio_dom_id = f"auto_audio_{st.session_state.autoplay_audio_id}"
        st.session_state.autoplay_pending = True

def pause_or_resume_audio():
    if st.session_state.audio_paused:
        st.session_state.audio_paused = False
        st.session_state.audio_command = "play"
    else:
        st.session_state.audio_paused = True
        st.session_state.audio_command = "pause"

def render_hidden_autoplay():
    if st.session_state.voice_enabled and st.session_state.autoplay_pending and st.session_state.autoplay_audio_b64:
        autoplay_attr = "" if st.session_state.audio_paused else "autoplay"
        audio_html = f"""
        <audio {autoplay_attr} style="display:none;" id="auto_audio_{st.session_state.autoplay_audio_id}">
            <source src="data:audio/mp3;base64,{st.session_state.autoplay_audio_b64}" type="audio/mp3">
        </audio>
        """
        st.markdown(audio_html, unsafe_allow_html=True)
        st.session_state.autoplay_pending = False

    if st.session_state.audio_command:
        command = st.session_state.audio_command
        js = f"""
        <script>
        (function() {{
            const audios = document.querySelectorAll("audio");
            audios.forEach((el) => {{
                try {{
                    if ("{command}" === "pause") {{
                        el.pause();
                    }} else if ("{command}" === "play") {{
                        el.play().catch(() => {{}});
                    }}
                }} catch (e) {{}}
            }});
        }})();
        </script>
        """
        st.markdown(js, unsafe_allow_html=True)
        st.session_state.audio_command = ""

def render_audio_player(audio_b64: str):
    if not audio_b64:
        return
    audio_html = f"""
    <audio controls>
        <source src="data:audio/mp3;base64,{audio_b64}" type="audio/mp3">
    </audio>
    """
    st.markdown(audio_html, unsafe_allow_html=True)

def add_assistant_message(text: str, auto_voice=True):
    text = to_simplified(text)
    audio_b64 = generate_tts_base64(text) if auto_voice else ""
    st.session_state.messages.append({
        "id": str(uuid.uuid4()),
        "role": "assistant",
        "content": text,
        "audio_b64": audio_b64
    })
    st.session_state.last_reply_text = text
    if audio_b64 and not st.session_state.audio_paused:
        set_latest_autoplay(audio_b64)

# =========================
# 14. 公共事务 Prompt
# =========================
def build_public_base_prompt(category_name: str, scene_name: str, policy_text: str):
    current_city = st.session_state.current_city or "未提供"
    current_district = st.session_state.current_district or "未提供"
    return f"""
你是一个专门帮助老人办理事务的中文助手，名字叫 乐龄伴。

请严格遵守：

【语言规则】
1. 只能使用简体中文
2. 统一使用“您”
3. 不要说“老人家”
4. 不要用太难的词
5. 一次不要说太多
6. 不要大段说明书式输出

【当前大类】
{category_name}

【当前场景】
{scene_name}

【当前地区】
城市：{current_city}
区域：{current_district}

【回答方式】
1. 先用一句安抚或接住情绪的话开头，但只能一次
2. 然后直接回答用户最担心的那个点
3. 一次只说 2 到 3 个最重要的点
4. 要像带老人办事，不要像背政策
5. 如果用户担心白跑、怕麻烦、看不懂、记不住，要先回应这个担心
6. 用户追问具体词是什么意思时，要直接解释，不要重复前一段
7. 回答尽量简短，适合老人一眼看懂
8. 最后用一句简单的话继续引导下一步
9. 结尾要根据不同问题变化，不能总是重复同一句
10. 开头也要根据不同问题变化，不能总是同一句
11. 尽量不要出现抽象说法，能具体就具体
12. 不要在同一段里重复“别着急、一步一步来、慢慢来”这类安抚语

【不要这样】
- 不要一次讲太多背景
- 不要反复重复同一句安抚话
- 不要堆很多“注意事项”
- 不要说抽象词，比如“相关材料”“有关证明”

【参考知识】
{policy_text}
"""

def _call_public_model(category_name: str, scene_name: str, user_input: str, policy_data: Dict[str, Any]):
    policy_text = build_policy_context(category_name, scene_name, policy_data)
    recent_history = build_recent_history(max_turns=8)

    if client is None:
        return "现在系统连接有点问题。您先别着急，您可以先问我带什么、去哪问、要不要先打电话这类最要紧的。"

    try:
        input_messages = [{"role": "system", "content": build_public_base_prompt(category_name, scene_name, policy_text)}]
        input_messages.extend(recent_history)
        input_messages.append({"role": "user", "content": user_input})

        response = client.responses.create(model="gpt-4.1-mini", input=input_messages)
        return to_simplified(response.output_text.strip())
    except Exception:
        return "这次我没答好。您先别急，您可以再问我一句最要紧的，比如先带什么。"

def answer_public_service(category_name: str, scene_name: str, user_input: str, policy_data: Dict[str, Any], intent: str = ""):
    raw = _call_public_model(category_name, scene_name, user_input, policy_data)
    return shorten_public_reply(raw, user_input, category_name, scene_name, intent)

# =========================
# 15. 陪伴聊天
# =========================
def answer_companion(user_input: str):
    recent_history = build_recent_history(max_turns=8)
    if client is None:
        return "我在呢，您慢慢说。"
    try:
        input_messages = [{
            "role": "system",
            "content": """
你是一个陪伴聊天机器人，名字叫 乐龄伴。

规则：
1. 只能用简体中文
2. 统一用“您”
3. 不要说“老人家”
4. 语气温和、自然
5. 回答要短
6. 多接住对方情绪
7. 不要一次说太多
8. 不要重复同一句安抚话
"""
        }]
        input_messages.extend(recent_history)
        input_messages.append({"role": "user", "content": user_input})
        response = client.responses.create(model="gpt-4.1-mini", input=input_messages)
        return to_simplified(response.output_text.strip())
    except Exception:
        return "我在呢，您慢慢说。"

# =========================
# 16. 核心处理逻辑
# =========================
def handle_user_input(user_text: str):
    user_text = user_text.strip()
    if not user_text:
        return

    user_text = to_simplified(user_text)
    policy_data = load_policy_knowledge()

    update_current_topic(user_text, policy_data)
    update_current_scene(user_text, policy_data)
    update_location_state(user_text)

    st.session_state.messages.append({
        "id": str(uuid.uuid4()),
        "role": "user",
        "content": user_text,
        "audio_b64": ""
    })

    new_category = detect_category_from_text(user_text, policy_data)
    new_scene = detect_scene_from_kb(user_text, policy_data)

    category_name = new_category
    scene_name = new_scene

    followup_intent = detect_followup_intent(user_text)
    st.session_state.current_intent = followup_intent

    if scene_name and not category_name:
        category_name = scene_belongs_to_category(scene_name, policy_data)

    if category_name:
        st.session_state.current_topic = category_name
    else:
        st.session_state.current_topic = ""

    if scene_name:
        st.session_state.current_scene = scene_name
    else:
        st.session_state.current_scene = ""

    update_service_progress(category_name, scene_name)

    if st.session_state.current_scene:
        detail_reply = answer_followup_detail(user_text, st.session_state.current_scene)
        if detail_reply:
            add_assistant_message(detail_reply, auto_voice=True)
            return

    if st.session_state.current_scene:
        finance_reply = answer_high_priority_finance_scene(user_text, st.session_state.current_scene)
        if finance_reply:
            add_assistant_message(finance_reply, auto_voice=True)
            return

    if detect_vague_expression(user_text) and not scene_name:
        reply = build_elder_guided_reply(
            user_text,
            "我先帮您分清楚是什么事。",
            ["您先告诉我是卡、钱，还是医院的事", "您说清一点，我就能更准地帮您", "我们一条一条来"],
            "",
            "",
            "general"
        )
        add_assistant_message(reply, auto_voice=True)
        return

    if detect_term_explain_request(user_text):
        term, term_reply = explain_service_term(user_text)
        if term_reply:
            reply = build_elder_guided_reply(
                user_text,
                f"我直接用白一点的话跟您说：{term_reply}",
                ["您先不用一下全记住", "先记住这个词大概是做什么的", "后面我还可以继续帮您看怎么做"],
                category_name,
                scene_name,
                "steps"
            )
            add_assistant_message(reply, auto_voice=True)
            return

    if detect_digital_help(user_text):
        reply = answer_digital_help(user_text)
        add_assistant_message(reply, auto_voice=True)
        return

    if detect_material_check_need(user_text):
        scene_for_material = scene_name or st.session_state.current_scene
        reply = build_material_check_reply(scene_for_material, user_text, policy_data)
        add_assistant_message(reply, auto_voice=True)
        return

    if category_name and not scene_name and is_public_service_category(category_name):
        reply = build_elder_guided_reply(
            "",
            "这类事我可以帮您慢慢分清楚。",
            ["您先告诉我是具体办什么", "如果方便，也可以告诉我在哪个城市", "我会一步一步陪您看"],
            category_name,
            "",
            "general"
        )
        add_assistant_message(reply, auto_voice=True)
        return

    if category_name and scene_name and is_public_service_category(category_name):
        if need_city_for_public_service(user_text, category_name) and not st.session_state.current_city:
            add_assistant_message(
                build_elder_guided_reply(
                    user_text,
                    "我先要知道您在哪个城市，后面才能跟您说得更准。",
                    ["您先告诉我城市", "再说您想办什么", "这样我更容易帮您缩小范围"],
                    category_name,
                    scene_name,
                    "location"
                ),
                auto_voice=True
            )
            return

        if ask_for_exact_location_or_hours(user_text):
            if not st.session_state.current_city:
                add_assistant_message(
                    build_elder_guided_reply(
                        user_text,
                        "您先告诉我您在哪个城市，我再帮您缩小范围。",
                        ["先说城市", "有区的话也可以一起说", "这样更不容易白跑"],
                        category_name,
                        scene_name,
                        "location"
                    ),
                    auto_voice=True
                )
                return

            if not has_precise_district():
                add_assistant_message(
                    build_elder_guided_reply(
                        user_text,
                        f"您现在说的是{st.session_state.current_city}，但具体地址和时间通常还要看区或具体服务点。",
                        ["您可以再告诉我所在的区", "如果没有区，也可以先打官方电话问", "这样更稳妥"],
                        category_name,
                        scene_name,
                        "location"
                    ),
                    auto_voice=True
                )
                return

        reply = answer_public_service(category_name, scene_name, user_text, policy_data, followup_intent)
        add_assistant_message(reply, auto_voice=True)
        return

    reply = answer_companion(user_text)
    add_assistant_message(reply, auto_voice=True)

# =========================
# 17. 新版布局
# =========================
left_col, right_col = st.columns([0.8, 2.6], gap="large")

with left_col:
    st.markdown(dedent("""
    <div class="left-panel">
        <div style="display:block; overflow:visible; margin-bottom:8px;">
            <div class="brand-title">乐龄伴</div>
        </div>
        <div class="brand-desc">
            字大清晰，按钮明显，操作更简单。<br>
            您可以问我：医保、退休、补贴、身份证、银行卡、反诈、微信操作这些事。
        </div>
    </div>
    """), unsafe_allow_html=True)

    page = st.radio("请选择页面", ["首页", "帮助", "设置"])

# =========================
# 18. 首页
# =========================
if page == "首页":
    with right_col:
        st.markdown("""
        <div class="hero-wrap">
            <div class="hero-title">乐龄伴</div>
            <div class="hero-subtitle">老年政策与办事智能助手</div>
            <div class="hero-desc">
                支持文字与语音提问，帮助您查询医保、退休、补贴政策和办理流程。
            </div>
            <div class="hero-guide">
                您可以点击下方常见问题，或直接输入、录音提问。
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div class="notice-banner">
            🌷 {st.session_state.today_greeting}
        </div>
        """, unsafe_allow_html=True)

        render_hidden_autoplay()

        st.markdown('<div class="section-title">常用快捷问法</div>', unsafe_allow_html=True)

        q1, q2, q3 = st.columns(3, gap="large")
        with q1:
            if st.button("医保报销怎么办", key="quick_1", use_container_width=True):
                handle_user_input("医保报销怎么办")
                st.rerun()

        with q2:
            if st.button("身份证能补办吗", key="quick_2", use_container_width=True):
                handle_user_input("我在北京住呢 我能不能在北京补办身份证")
                st.rerun()

        with q3:
            if st.button("退休怎么办理", key="quick_3", use_container_width=True):
                handle_user_input("退休怎么办理")
                st.rerun()

        st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)

        # 聊天区域
        chat_area = st.container()

        with chat_area:
            for message in st.session_state.messages:
                text = (message.get("content") or "").strip()
                if not text:
                    continue

                if message["role"] == "user":
                    st.markdown(
                        f'<div class="user-bubble">🗨️ 您：{text}</div>',
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(
                        f'<div class="assistant-bubble">🧡 {text}</div>',
                        unsafe_allow_html=True
                    )
                    if message.get("audio_b64"):
                        render_audio_player(message["audio_b64"])

        st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

        if st.session_state.current_city or st.session_state.current_scene or st.session_state.current_topic:
            tag_city = st.session_state.current_city or "当前"
            tag_scene = st.session_state.current_scene or st.session_state.current_topic or "服务流程"
            st.markdown(
                f'<div class="answer-tag">{tag_city}｜{tag_scene}</div>',
                unsafe_allow_html=True
            )

        if st.session_state.current_scene:
            st.markdown(
                f'<div class="answer-title">{st.session_state.current_scene}</div>',
                unsafe_allow_html=True
            )
        elif st.session_state.current_topic:
            st.markdown(
                f'<div class="answer-title">{st.session_state.current_topic}</div>',
                unsafe_allow_html=True
            )

        demo_steps = []
        if st.session_state.current_scene == "医保报销":
            demo_steps = ["准备身份证和医保卡", "前往指定医院或线上平台", "提交报销材料", "等待审核结果"]
        elif st.session_state.current_scene == "退休办理":
            demo_steps = ["确认是否达到退休条件", "准备身份证和社保相关材料", "前往社保机构办理", "等待审核和养老金发放"]
        elif st.session_state.current_scene == "身份证补办":
            demo_steps = ["准备户口本或相关身份证明", "前往当地公安机关受理点", "提交补办申请", "等待新证制作完成"]
        elif st.session_state.current_scene == "社保卡补办":
            demo_steps = ["确认卡片是否需要先挂失", "准备身份证", "前往社保或合作银行网点", "等待补卡完成"]
        elif st.session_state.current_scene == "异地就医":
            demo_steps = ["先确认是否需要备案", "准备医保相关信息", "按当地要求办理异地就医备案", "就医后按规定结算或报销"]

        if demo_steps:
            for i, step in enumerate(demo_steps, start=1):
                st.markdown(f"""
                <div class="step-row">
                    <div class="step-num">{i}</div>
                    <div class="step-text">{step}</div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown(
                '<div class="tip-box">⚠️ 温馨提醒：不同区县办理要求可能略有不同，出门前最好先电话确认。</div>',
                unsafe_allow_html=True
            )

        user_text = st.text_input(
            "请输入您的问题",
            key=f"main_input_{st.session_state.input_counter}",
            label_visibility="collapsed",
            placeholder="请在这里输入您的问题，例如：我在北京住，能不能在北京补办身份证？"
        )

        audio = None
        send_btn = False
        read_btn = False

        if st.session_state.voice_processing:
            st.info("正在识别语音，请稍等...")
        else:
            b1, b2, b3 = st.columns([1, 1, 1], gap="medium")

            with b1:
                audio = mic_recorder(
                    start_prompt="语音",
                    stop_prompt="停止",
                    key="main_mic_recorder_v2",
                    use_container_width=True
                )

            with b2:
                send_btn = st.button("发送", key="send_btn_v2", use_container_width=True)

            with b3:
                pause_label = "继续朗读" if st.session_state.audio_paused else "暂停朗读"
                read_btn = st.button(pause_label, key="read_btn_v2", use_container_width=True)



        if send_btn and user_text.strip():
            handle_user_input(user_text)
            st.session_state.input_counter += 1
            st.rerun()

        if read_btn:
            pause_or_resume_audio()
            st.rerun()

        if audio and not st.session_state.voice_processing:
            audio_bytes = audio["bytes"]
            voice_sig = hashlib.md5(audio_bytes).hexdigest()

            if voice_sig != st.session_state.last_voice_sig:
                st.session_state.voice_processing = True
                st.session_state.last_voice_sig = voice_sig
                st.session_state.pending_audio_bytes = audio_bytes
                st.rerun()

        if st.session_state.voice_processing and "pending_audio_bytes" in st.session_state:
            audio_bytes = st.session_state.pending_audio_bytes
            audio_path = None

            try:
                if client is None:
                    st.error("当前没有检测到 OPENAI_API_KEY，暂时无法进行语音识别。")
                else:
                    mime_type = "audio/webm"
                    suffix = ".webm"

                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
                        f.write(audio_bytes)
                        audio_path = f.name

                    with open(audio_path, "rb") as f:
                        transcript = client.audio.transcriptions.create(
                            model="whisper-1",
                            file=f
                        )

                    voice_text = transcript.text.strip()
                    voice_text = to_simplified(voice_text)

                    if voice_text:
                        handle_user_input(voice_text)
                        st.session_state.input_counter += 1
                    else:
                        st.warning("识别完成了，但没有得到文字结果。")

            except Exception as e:
                st.error("语音识别失败：" + str(e))

            finally:
                st.session_state.voice_processing = False
                del st.session_state["pending_audio_bytes"]
                if audio_path and os.path.exists(audio_path):
                    os.remove(audio_path)
                st.rerun()
# =========================
# 19. 帮助页
# =========================
elif page == "帮助":
    with right_col:
        st.title("帮助")
        st.write("您可以直接这样问我：")
        st.write("- 我在北京住，能不能在北京补办身份证")
        st.write("- 医保报销怎么办")
        st.write("- 退休怎么办理")
        st.write("- 社保卡丢了带什么")
        st.write("- 银行卡冻结怎么办")
        st.write("- 验证码在哪看")
        st.write("- 小程序怎么进")
        st.write("- 其他身份证明材料是什么意思")

        st.markdown("### 这版会怎么帮您")
        st.write("- 先接住您的担心")
        st.write("- 再只说最要紧的两三样")
        st.write("- 不一下说太多")
        st.write("- 最后继续带您下一步")
        st.write("- 不会在一段里重复说好几次“别着急”")
        st.write("- 不同问题会有不同的开头和不同的下一步引导")

        st.markdown("### 语音功能")
        st.write("- 点击“录音提问”可以直接说话")
        st.write("- 点击“暂停朗读”可以暂停自动播报")
        st.write("- 再点一次可以继续朗读")

# =========================
# 20. 设置页
# =========================
elif page == "设置":
    with right_col:
        st.title("设置")

        st.markdown("### 字体大小")
        font_choice = st.radio(
            "请选择字号",
            ["标准字", "大字", "超大字"],
            index=["标准字", "大字", "超大字"].index(st.session_state.font_size_mode),
            horizontal=True
        )
        if font_choice != st.session_state.font_size_mode:
            st.session_state.font_size_mode = font_choice
            st.rerun()

        st.markdown("### 语音功能")
        voice_enabled = st.toggle("开启语音朗读", value=st.session_state.voice_enabled)
        st.session_state.voice_enabled = voice_enabled

        st.markdown("### API 状态")
        if api_key:
            st.success("已检测到 OPENAI_API_KEY")
        else:
            st.error("未检测到 OPENAI_API_KEY，请检查 .env 文件")

        st.markdown("### 当前说明")
        st.write("这版重点是：所有回答都更适合老人阅读和听。")
        st.write("会先安抚，再说最要紧的，不会一下说太多。")
        st.write("同一段里不会重复多次说“别着急”。")
        st.write("不同问题会给不同的开头和不同的下一步引导。")