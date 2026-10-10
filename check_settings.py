from app.core.config import settings

print("MS_TARGET_MAILBOX:", settings.MS_TARGET_MAILBOX)
print("All fields:", [f for f in settings.model_fields])
