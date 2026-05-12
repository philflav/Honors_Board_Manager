The script must output a 'carousel_config.json' file using a hierarchical "Group" structure:

globalConfig: Set a fallbackDurationMs of 8000.

categories: Array of objects (Mens, Ladies, Mixed).

groups: Within each category, images must be organized into "groups" (e.g., "Summer_Collection", "Flash_Sale").

Group Properties: Each group object must include 'groupId', 'groupName', and 'sharedProperties' (e.g., 'backgroundColor', 'themeTag').

Image Objects: Within each group's 'images' array:

'id': Unique string.

'url': Local file path.

'durationMs': (Optional) Specific override. If omitted, the app should fall back to the category default.

Ensure the generator script logic allows for multiple groups per category, ensuring images that "belong together" are always contiguous in the JSON array.