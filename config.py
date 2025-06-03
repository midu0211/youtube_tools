# config.py

# --- Authentication & API ---
CLIENT_SECRETS_FILE = 'client_secret.json'
TOKEN_PICKLE_FILE = 'token.pickle' 
# Define individual scope groups
UPLOAD_SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
READONLY_SCOPES = ['https://www.googleapis.com/auth/youtube.readonly']
COMMENT_SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']

# Combine all scopes needed by the application for initial authentication
# Ensure no duplicates and convert to list
ALL_APP_SCOPES = list(set(UPLOAD_SCOPES + READONLY_SCOPES + COMMENT_SCOPES))

API_SERVICE_NAME = 'youtube'
API_VERSION = 'v3'

# --- File Paths ---
SCHEDULED_POSTS_FILE = 'scheduled_posts.json'
COMMENT_TEMPLATES_FILE = 'comment_templates.json'

# --- Timezone ---
VIETNAM_TZ_STR = 'Asia/Ho_Chi_Minh'

# --- Comment Generation ---
MEANINGFUL_COMMENT_BASES = [
    "Video tuyệt vời!", "Nội dung rất hay, cảm ơn bạn đã chia sẻ.", "Mình rất thích video này.",
    "Làm tốt lắm! Tiếp tục phát huy nhé.", "Video này thật sự hữu ích.", "Chất lượng video tuyệt vời.",
    "Wow, ấn tượng thật!", "Cảm ơn vì những thông tin giá trị.", "Rất sáng tạo!", "Hay lắm bạn ơi!",
    "Xem xong thấy có thêm động lực. Cảm ơn bạn!", "Chúc mừng bạn đã có một video thành công!", "Yêu bạn!",
    "Quá đỉnh!", "Hay quá đi mất!", "Tuyệt vời! Bạn làm rất tốt.", "Video này xứng đáng triệu view!", "Tuyệt cú mèo!",
    "Tuyệt!", "Hay!", "Chất!", "Đỉnh!", "Oke bạn ơi.", "Thích nha.", "Good job!", "Amazing!", "Perfect!", "Awesome!",
    "Cảm ơn bạn nhiều.", "Thanks for sharing!", "Rất biết ơn bạn.", "Cảm ơn vì đã làm video này.", "Thank you!",
    "Video hay, tiếp tục phát huy nhé kênh.", "Nội dung chất lượng, mình đã sub kênh.", "Video ý nghĩa quá.",
    "Mình đã học được nhiều điều từ video này.", "Xem giải trí mà vẫn có kiến thức.", "Đúng thứ mình đang tìm."
]
EMOJIS_LIST = ["👍", "❤️", "🎉", "💯", "🔥", "😮", "😂", "✨", "🌟", "😊", "😃", "😍", "🙏", "🙌", "👌", "💖", "🤣", "🤩"]
COMMENT_SUFFIXES = [
    "Rất mong video tiếp theo của bạn!", "Cố gắng lên nhé!", "Chúc kênh ngày càng phát triển!",
    "Tuyệt vời ông mặt trời!", "Luôn ủng hộ bạn!", "5 sao cho video này!"
]