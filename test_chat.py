import sys
sys.stdout.reconfigure(encoding='utf-8')

from core.ai_chat import AIChatInterface

print("=== AI Chat Interface Test ===\n")

chat = AIChatInterface()

# Test send message
response = chat.send("Hello, can you analyze this video?")
print(f"User: Hello, can you analyze this video?")
print(f"AI: {response}\n")

# Test with metadata
response = chat.send("Find highlights from this clip", {"video_path": "test.mp4"})
print(f"User: Find highlights from this clip")
print(f"AI: {response}\n")

# Test history
print("=== Chat History ===")
for msg in chat.get_history():
    print(f"[{msg['role']}] {msg['content'][:60]}...")

print("\n=== Test Complete ===")
