"""
Main Chatbot Interface - Natural Language Business Data Query System
"""

from query_orchestrator import QueryOrchestrator
import config

class BusinessChatbot:
    def __init__(self):
        print("\n" + "="*60)
        print("Business Data Chatbot")
        print("="*60)
        print("Initializing...")
        
        self.orchestrator = QueryOrchestrator()
        
        print("✓ Ready!")
        print("\nAsk questions about your business data in natural language.")
        print("Type 'exit' or 'quit' to end the session.\n")
        print("="*60 + "\n")
    
    def run(self):
        """Main chat loop"""
        while True:
            try:
                # Get user input
                user_input = input("You: ").strip()
                
                # Check for exit
                if user_input.lower() in ['exit', 'quit', 'q']:
                    print("\nGoodbye! 👋")
                    break
                
                if not user_input:
                    continue
                
                # Process query
                result = self.orchestrator.process_query(user_input)
                
                # Display results
                print("\nChatbot:")
                if result['success']:
                    print(result['formatted_output'])
                else:
                    print(f"❌ Error: {result.get('error', 'Unknown error')}")
                
                print("\n" + "-"*60 + "\n")
                
            except KeyboardInterrupt:
                print("\n\nGoodbye! 👋")
                break
            except Exception as e:
                print(f"\n❌ Error: {str(e)}\n")

def main():
    """Entry point"""
    try:
        chatbot = BusinessChatbot()
        chatbot.run()
    except Exception as e:
        print(f"\n❌ Failed to start chatbot: {str(e)}")
        print("\nPlease ensure:")
        print("1. Database is created (run: python db_manager.py)")
        print("2. Schema is generated (run: python schema_analyzer.py)")
        print("3. Azure OpenAI credentials are configured in config.py")

if __name__ == "__main__":
    main()
