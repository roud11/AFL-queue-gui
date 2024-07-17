class Filter:
    def __init__(self, parsed_files):
        self.parsed_files = parsed_files

    def search_by_id(self, search_term):
        if not search_term.isdigit():
            raise ValueError("The identifier must be a numeric value")

        matching_items = [
            file_dict for file_dict in self.parsed_files
            if search_term.lower() in str(file_dict.get('id', '')).lower()
        ]

        return matching_items
