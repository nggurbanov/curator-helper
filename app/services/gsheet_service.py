# app/services/gsheet_service.py
"""
Handles all interactions with Google Sheets using the gspread library.
- Initializes gspread client with service account credentials.
- Reads FAQ question-answer pairs from a specified sheet.
- Reads and writes settings (key-value pairs) from/to a "BotSettings" sheet.
- Manages creation of the "BotSettings" sheet if it doesn't exist.
"""

import logging
import gspread
from gspread.exceptions import SpreadsheetNotFound, WorksheetNotFound, APIError
from typing import List, Dict, Tuple, Optional, Any

from app import config

logger = logging.getLogger(__name__)

class GSheetService:
    """
    Service class for interacting with Google Sheets.
    """
    def __init__(self, credentials_path: str = str(config.GSPREAD_KEY_FILE_PATH)):
        """
        Initializes the GSheetService with gspread credentials.

        Args:
            credentials_path: Path to the Google Service Account JSON key file.
        """
        self.gc = None
        try:
            self.gc = gspread.service_account(filename=credentials_path)
            logger.info("GSpread client initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize GSpread client with {credentials_path}: {e}")

    def _get_spreadsheet(self, gsheet_url: str) -> Optional[gspread.Spreadsheet]:
        """Helper to open a spreadsheet by URL."""
        if not self.gc:
            logger.error("GSpread client not initialized. Cannot open spreadsheet.")
            return None
        try:
            spreadsheet = self.gc.open_by_url(gsheet_url)
            logger.debug(f"Successfully opened spreadsheet: {gsheet_url}")
            return spreadsheet
        except SpreadsheetNotFound:
            logger.error(f"Spreadsheet not found at URL: {gsheet_url}")
            return None
        except APIError as e:
            logger.error(f"APIError opening spreadsheet {gsheet_url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error opening spreadsheet {gsheet_url}: {e}")
            return None

    def _get_worksheet(self, spreadsheet: gspread.Spreadsheet, sheet_name: str, create_if_not_exists: bool = False, headers: Optional[List[str]] = None) -> Optional[gspread.Worksheet]:
        """Helper to get a worksheet by name, optionally creating it."""
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
            logger.debug(f"Successfully opened worksheet: {sheet_name}")
            return worksheet
        except WorksheetNotFound:
            if create_if_not_exists:
                logger.info(f"Worksheet '{sheet_name}' not found. Attempting to create it.")
                try:
                    worksheet = spreadsheet.add_worksheet(title=sheet_name, rows="100", cols="20")
                    if headers:
                        worksheet.append_row(headers)
                        logger.info(f"Worksheet '{sheet_name}' created successfully with headers: {headers}")
                    else:
                        logger.info(f"Worksheet '{sheet_name}' created successfully.")
                    return worksheet
                except APIError as e_create:
                    logger.error(f"APIError creating worksheet '{sheet_name}': {e_create}")
                    return None
                except Exception as e_create_unexp:
                    logger.error(f"Unexpected error creating worksheet '{sheet_name}': {e_create_unexp}")
                    return None
            else:
                logger.warning(f"Worksheet '{sheet_name}' not found and create_if_not_exists is False.")
                return None
        except APIError as e:
            logger.error(f"APIError opening worksheet {sheet_name}: {e}")
            return None
        except Exception as e_unexp:
            logger.error(f"Unexpected error opening worksheet {sheet_name}: {e_unexp}")
            return None

    def check_spreadsheet_access(self, gsheet_url: str) -> Tuple[bool, Optional[str]]:
        """
        Checks if the bot can access the spreadsheet and has basic read permissions.
        Also attempts to list worksheets as a proxy for some level of access.

        Args:
            gsheet_url: The URL of the Google Sheet.

        Returns:
            A tuple (bool, Optional[str]) indicating (access_granted, error_message_or_None).
        """
        spreadsheet = self._get_spreadsheet(gsheet_url)
        if not spreadsheet:
            return False, "Spreadsheet not found or could not be accessed. Please check the URL and share settings."
        try:
            _ = spreadsheet.worksheets()
            return True, None
        except APIError as e:
            logger.error(f"APIError during access check for {gsheet_url}: {e}")
            if 'PERMISSION_DENIED' in str(e):
                return False, "Permission denied. Please ensure the bot's service account email has at least 'Viewer' access to the Google Sheet."
            return False, f"An API error occurred while checking access: {e}"
        except Exception as e:
            logger.error(f"Unexpected error during access check for {gsheet_url}: {e}")
            return False, f"An unexpected error occurred: {e}"


    def read_faqs(self, gsheet_url: str, faq_sheet_name: str) -> Optional[List[Tuple[str, str]]]:
        """
        Reads FAQ question-answer pairs from a specified sheet in a GSheet.
        Assumes FAQs are in the first two columns (Question, Answer).

        Args:
            gsheet_url: The URL of the Google Sheet.
            faq_sheet_name: The name of the sheet containing FAQs.

        Returns:
            A list of (question, answer) tuples, or None if an error occurs.
        """
        spreadsheet = self._get_spreadsheet(gsheet_url)
        if not spreadsheet:
            return None
        
        worksheet = self._get_worksheet(spreadsheet, faq_sheet_name)
        if not worksheet:
            return None

        try:
            all_values = worksheet.get_all_values()
            if not all_values:
                logger.info(f"FAQ sheet '{faq_sheet_name}' in {gsheet_url} is empty.")
                return []

            faqs = []
            start_row = 0
            if all_values and len(all_values[0]) >= 2 and \
               (all_values[0][0].lower().strip() == "вопрос" or all_values[0][0].lower().strip() == "question"):
                start_row = 1

            for row in all_values[start_row:]:
                if len(row) >= 2:
                    question = row[0].strip()
                    answer = row[1].strip()
                    if question and answer:
                        faqs.append((question, answer))
            logger.info(f"Successfully read {len(faqs)} FAQs from '{faq_sheet_name}'.")
            return faqs
        except APIError as e:
            logger.error(f"APIError reading FAQs from '{faq_sheet_name}': {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error reading FAQs from '{faq_sheet_name}': {e}")
            return None

    def read_settings_sheet(self, gsheet_url: str, settings_sheet_name: str) -> Optional[Dict[str, Any]]:
        """
        Reads settings (key-value pairs) from the "BotSettings" sheet.
        Assumes settings are in two columns (Key, Value).

        Args:
            gsheet_url: The URL of the Google Sheet.
            settings_sheet_name: The name of the sheet containing bot settings.

        Returns:
            A dictionary of settings, or None if an error occurs.
        """
        spreadsheet = self._get_spreadsheet(gsheet_url)
        if not spreadsheet:
            return None

        worksheet = self._get_worksheet(spreadsheet, settings_sheet_name)
        if not worksheet:
            logger.warning(f"Settings sheet '{settings_sheet_name}' not found in {gsheet_url} for reading.")
            return None

        try:
            all_values = worksheet.get_all_values()
            settings_dict = {}
            if not all_values:
                logger.info(f"Settings sheet '{settings_sheet_name}' in {gsheet_url} is empty.")
                return {}

            start_row = 0
            if all_values and len(all_values[0]) >= 2 and \
               (all_values[0][0].lower().strip() == "setting" or all_values[0][0].lower().strip() == "key"):
                start_row = 1

            for row in all_values[start_row:]:
                if len(row) >= 2:
                    key = row[0].strip()
                    value_str = row[1].strip()
                    if key:
                        if value_str.lower() == 'true':
                            value = True
                        elif value_str.lower() == 'false':
                            value = False
                        elif value_str.isdigit():
                            value = int(value_str)
                        elif '.' in value_str and all(part.isdigit() for part in value_str.split('.', 1)):
                            try:
                                value = float(value_str)
                            except ValueError:
                                value = value_str
                        else:
                            value = value_str
                        settings_dict[key] = value
            logger.info(f"Successfully read {len(settings_dict)} settings from '{settings_sheet_name}'.")
            return settings_dict
        except APIError as e:
            logger.error(f"APIError reading settings from '{settings_sheet_name}': {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error reading settings from '{settings_sheet_name}': {e}")
            return None

    def write_settings_sheet(self, gsheet_url: str, settings_sheet_name: str, settings_data: Dict[str, Any], default_settings_schema: Dict[str, Any]) -> bool:
        """
        Writes settings to the "BotSettings" sheet. Creates the sheet if it doesn't exist.
        Overwrites the entire sheet with the provided settings_data, ordered by default_settings_schema.

        Args:
            gsheet_url: The URL of the Google Sheet.
            settings_sheet_name: The name of the sheet for bot settings.
            settings_data: A dictionary of settings to write.
            default_settings_schema: A dictionary of default settings, used for ordering and ensuring all keys are present.

        Returns:
            True if successful, False otherwise.
        """
        spreadsheet = self._get_spreadsheet(gsheet_url)
        if not spreadsheet:
            return False

        headers = ["Setting Key", "Setting Value"]
        worksheet = self._get_worksheet(spreadsheet, settings_sheet_name, create_if_not_exists=True, headers=headers)
        if not worksheet:
            logger.error(f"Failed to get or create settings sheet '{settings_sheet_name}' in {gsheet_url}.")
            return False

        try:
            worksheet.clear()

            data_to_write = []
            for key in default_settings_schema.keys():
                value = settings_data.get(key, default_settings_schema.get(key))
                value_str = str(value) if value is not None else ""
                data_to_write.append([key, value_str])
            
            for key, value in settings_data.items():
                if key not in default_settings_schema:
                    value_str = str(value) if value is not None else ""
                    data_to_write.append([key, value_str])


            if data_to_write:
                worksheet.append_rows(data_to_write, value_input_option='USER_ENTERED')
            
            logger.info(f"Successfully wrote {len(data_to_write)} settings to '{settings_sheet_name}'.")
            return True
        except APIError as e:
            logger.error(f"APIError writing settings to '{settings_sheet_name}': {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error writing settings to '{settings_sheet_name}': {e}")
            return False

if __name__ == '__main__':
    print("GSheetService Test Block")
    print("------------------------")
    print(f"Attempting to use GSpread key from: {config.GSPREAD_KEY_FILE_PATH}")

    if not config.GSPREAD_KEY_FILE_PATH.exists():
        print("CRITICAL: GSpread key file not found. Cannot run tests.")
        exit()

    service = GSheetService()
    if not service.gc:
        print("GSpread client initialization failed. Exiting tests.")
        exit()

    TEST_GSHEET_URL = "YOUR_TEST_GOOGLE_SHEET_URL_HERE"
    if TEST_GSHEET_URL == "YOUR_TEST_GOOGLE_SHEET_URL_HERE":
        print("\nPlease set TEST_GSHEET_URL in the __main__ block of gsheet_service.py to run tests.")
        exit()

    TEST_FAQ_SHEET_NAME = "TestFAQs"
    TEST_SETTINGS_SHEET_NAME = "TestBotSettings"
    
    print(f"\n0. Testing access to: {TEST_GSHEET_URL}")
    access_ok, access_msg = service.check_spreadsheet_access(TEST_GSHEET_URL)
    if access_ok:
        print("   Access check successful.")
    else:
        print(f"   Access check failed: {access_msg}")
        print("   Cannot proceed with further tests if access fails.")
        exit()


    print(f"\n1. Testing write_settings_sheet to '{TEST_SETTINGS_SHEET_NAME}'...")
    from app.services.config_manager import get_default_settings as get_bot_default_settings
    current_defaults = get_bot_default_settings()
    
    test_settings_data = current_defaults.copy()
    test_settings_data["gsheet_url"] = TEST_GSHEET_URL
    test_settings_data["personality_prompt_name"] = "test_override_prompt.txt"
    test_settings_data["anonq_enabled"] = False
    test_settings_data["custom_test_setting"] = "This is a test value from gsheet_service"


    if service.write_settings_sheet(TEST_GSHEET_URL, TEST_SETTINGS_SHEET_NAME, test_settings_data, current_defaults):
        print(f"   Successfully wrote settings to '{TEST_SETTINGS_SHEET_NAME}'.")
    else:
        print(f"   Failed to write settings to '{TEST_SETTINGS_SHEET_NAME}'.")

    # 2. Test reading settings
    print(f"\n2. Testing read_settings_sheet from '{TEST_SETTINGS_SHEET_NAME}'...")
    read_settings = service.read_settings_sheet(TEST_GSHEET_URL, TEST_SETTINGS_SHEET_NAME)
    if read_settings is not None:
        print(f"   Read settings: {read_settings}")
        # Basic check
        if read_settings.get("personality_prompt_name") == "test_override_prompt.txt":
            print("   Read-back of 'personality_prompt_name' successful.")
        if read_settings.get("anonq_enabled") == False: # Note: bool comparison
             print("   Read-back of 'anonq_enabled' successful.")
        if read_settings.get("custom_test_setting") == "This is a test value from gsheet_service":
            print("   Read-back of 'custom_test_setting' successful.")

    else:
        print(f"   Failed to read settings from '{TEST_SETTINGS_SHEET_NAME}'.")

    # 3. Test reading FAQs (Manually create a sheet named TestFAQs with some data for this)
    # Example TestFAQs sheet content:
    # Question,Answer
    # What is your name?,TestBot
    # How are you?,I am fine.
    print(f"\n3. Testing read_faqs from '{TEST_FAQ_SHEET_NAME}'...")
    print(f"   (Ensure you have a sheet named '{TEST_FAQ_SHEET_NAME}' in {TEST_GSHEET_URL} with Q/A in first two columns)")
    faqs = service.read_faqs(TEST_GSHEET_URL, TEST_FAQ_SHEET_NAME)
    if faqs is not None:
        print(f"   Read {len(faqs)} FAQs:")
        for q, a in faqs:
            print(f"     Q: {q}, A: {a}")
    else:
        print(f"   Failed to read FAQs from '{TEST_FAQ_SHEET_NAME}'. This might be normal if the sheet doesn't exist or is empty.")

    print("\n--- GSheetService Tests Complete ---")

