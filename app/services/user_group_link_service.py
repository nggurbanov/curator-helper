import shelve
import logging
from pathlib import Path
from typing import Dict, Optional, Union

logger = logging.getLogger(__name__)

class UserGroupLinkService:
    """
    Manages the mapping between users and their designated group chats
    for anonymous messaging, using a shelve database.
    """
    DEFAULT_SHELF_KEY = "user_group_links"

    def __init__(self, shelf_file_path: Union[str, Path], shelf_key: str = DEFAULT_SHELF_KEY):
        self.shelf_file_path = Path(shelf_file_path)
        self.shelf_key = shelf_key

    def _get_links_dict(self) -> Dict[int, int]:
        """Opens the shelf and returns the links dictionary, or an empty one if not found."""
        try:
            with shelve.open(str(self.shelf_file_path)) as db:
                return db.get(self.shelf_key, {})
        except Exception as e:
            logger.error(f"Error accessing shelve file {self.shelf_file_path} to get links: {e}")
            return {}

    def _save_links_dict(self, links_dict: Dict[int, int]) -> bool:
        """Saves the provided links dictionary to the shelf."""
        try:
            self.shelf_file_path.parent.mkdir(parents=True, exist_ok=True)
            with shelve.open(str(self.shelf_file_path)) as db:
                db[self.shelf_key] = links_dict
            logger.debug(f"Saved user-group links to key '{self.shelf_key}' in {self.shelf_file_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving links to shelve file {self.shelf_file_path}: {e}")
            return False

    def set_user_group_link(self, user_id: int, group_id: int) -> bool:
        """
        Sets or updates the group chat link for a given user.
        Returns True on success, False on failure.
        """
        if not isinstance(user_id, int) or not isinstance(group_id, int):
            logger.warning(f"Attempted to set link with non-integer IDs: user_id={user_id}, group_id={group_id}")
            return False
        
        links = self._get_links_dict()
        links[user_id] = group_id
        return self._save_links_dict(links)

    def get_group_id_for_user(self, user_id: int) -> Optional[int]:
        """
        Retrieves the group chat ID linked to the given user ID.
        Returns the group_id if found, else None.
        """
        if not isinstance(user_id, int):
            logger.warning(f"Attempted to get group ID with non-integer user_id: {user_id}")
            return None
        
        links = self._get_links_dict()
        return links.get(user_id)

    def remove_user_group_link(self, user_id: int) -> bool:
        """
        Removes the group chat link for a given user.
        Returns True if a link was removed/didn't exist and save was successful (or not needed), False on save failure.
        """
        if not isinstance(user_id, int):
            logger.warning(f"Attempted to remove link with non-integer user_id: {user_id}")
            return False

        links = self._get_links_dict()
        if user_id in links:
            del links[user_id]
            logger.info(f"Removed group link for user_id: {user_id} from key '{self.shelf_key}'.")
            return self._save_links_dict(links)
        logger.info(f"No group link found to remove for user_id: {user_id} in key '{self.shelf_key}'.")
        return True 