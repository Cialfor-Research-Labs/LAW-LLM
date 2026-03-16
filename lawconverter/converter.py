import json
import re

class LawConverter:
    def __init__(self, json_filepath):
        """Loads the JSON mapping file."""
        try:
            with open(json_filepath, 'r', encoding='utf-8') as file:
                self.mapping_data = json.load(file)
        except FileNotFoundError:
            print(f"\n❌ Error: Could not find '{json_filepath}'.")
            print("Please make sure the JSON file is in the exact same folder as this script.\n")
            self.mapping_data = []

    def _format_result(self, item):
        """Formats a single JSON entry into a readable string."""
        return (f"  • IPC Section: {item['ipc_section']}\n"
                f"  • BNS Section: {item['bns_section']}\n"
                f"  • Subject:     {item['subject']}\n")

    def _normalize_token(self, token):
        token = token or ''
        return re.sub(r'\s+', '', token).lower()

    def _extract_tokens(self, field_value):
        field_value = field_value or ''
        normalized = field_value.replace('&', ',').replace(';', ',')
        return [token.strip() for token in normalized.split(',') if token.strip()]

    def find_by_field(self, field_name, query):
        normalized_query = self._normalize_token(query)
        matches = []

        for item in self.mapping_data:
            tokens = self._extract_tokens(item.get(field_name, ''))
            if any(self._normalize_token(token) == normalized_query for token in tokens):
                matches.append(item)

        return matches

    def search_ipc_to_bns(self, ipc_query):
        print(f"\n--- Results for IPC Section: {ipc_query} ---")
        results = self.find_by_field('ipc_section', ipc_query)

        if results:
            for res in results:
                print(self._format_result(res))
        else:
            print("  No match found in the database.")

    def search_bns_to_ipc(self, bns_query):
        print(f"\n--- Results for BNS Section: {bns_query} ---")
        results = self.find_by_field('bns_section', bns_query)

        if results:
            for res in results:
                print(self._format_result(res))
        else:
            print("  No match found in the database.")

    def search_by_subject(self, keyword):
        print(f"\n--- Subject Search Results for: '{keyword}' ---")
        results = []
        
        for item in self.mapping_data:
            if keyword.lower() in item['subject'].lower():
                results.append(item)
                
        if results:
            print(f"  Found {len(results)} match(es):\n")
            for res in results:
                print(self._format_result(res))
        else:
            print("  No match found in the database.")

# ==========================================
# Interactive Menu
# ==========================================
def main():
    # Initialize the converter
    converter = LawConverter('bns_ipc_mapping.json')
    
    # If the file didn't load, stop the script
    if not converter.mapping_data:
        return

    while True:
        print("\n" + "="*40)
        print(" BNS - IPC LAW CONVERTER ")
        print("="*40)
        print("1. Convert old IPC to new BNS")
        print("2. Convert new BNS to old IPC")
        print("3. Search by Keyword/Subject (e.g., 'theft')")
        print("4. Exit")
        print("="*40)
        
        choice = input("Enter your choice (1-4): ").strip()
        
        if choice == '1':
            query = input("Enter the IPC Section number (e.g., 420): ")
            converter.search_ipc_to_bns(query)
            
        elif choice == '2':
            query = input("Enter the BNS Section number (e.g., 318(4)): ")
            converter.search_bns_to_ipc(query)
            
        elif choice == '3':
            query = input("Enter a keyword to search for: ")
            converter.search_by_subject(query)
            
        elif choice == '4':
            print("\nExiting the converter. Have a great day!\n")
            break
            
        else:
            print("\nInvalid choice. Please enter a number between 1 and 4.")
            
        # Pause before clearing the screen for the next menu loop
        input("\nPress Enter to continue...")

if __name__ == "__main__":
    main()
