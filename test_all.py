import sys
sys.stdout.reconfigure(encoding='utf-8')

# Test API imports
try:
    from api.main import app
    print("✓ FastAPI app loaded successfully")
except Exception as e:
    print(f"✗ Failed to load app: {e}")

# Test core modules
try:
    from core.ai_chat import AIChatInterface
    chat = AIChatInterface()
    print("✓ AI Chat Interface loaded successfully")
except Exception as e:
    print(f"✗ Failed to load AI Chat: {e}")

try:
    from core.database import Database
    db = Database()
    print("✓ Database loaded successfully")
except Exception as e:
    print(f"✗ Failed to load Database: {e}")

try:
    from analyzers.text_analyzer import TextAnalyzer
    analyzer = TextAnalyzer()
    print("✓ Text Analyzer loaded successfully")
except Exception as e:
    print(f"✗ Failed to load Text Analyzer: {e}")

try:
    from analyzers.image_analyzer import ImageAnalyzer
    analyzer = ImageAnalyzer()
    print("✓ Image Analyzer loaded successfully")
except Exception as e:
    print(f"✗ Failed to load Image Analyzer: {e}")

try:
    from core.pipeline_manager import PipelineManager
    manager = PipelineManager()
    print("✓ Pipeline Manager loaded successfully")
except Exception as e:
    print(f"✗ Failed to load Pipeline Manager: {e}")

print("\n=== All modules loaded successfully! ===")
