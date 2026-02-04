"""Base application class for Badge Launcher apps.

All applications should inherit from this class and implement
the required methods: enter() and exit().
"""

class App:
    """Base class for all Badge applications.

    Attributes:
        name: Display name of the application (shown in menu)
    """

    def __init__(self, name):
        """Initialize the application.

        Args:
            name: Display name for the application
        """
        self.name = name

    def enter(self, on_exit=None):
        """Called when the app is launched.

        This method should:
        - Create and display the app's UI
        - Set up event handlers
        - Initialize any resources

        Args:
            on_exit: Optional callback to call when exiting
        """
        pass

    def exit(self):
        """Called when the app is exiting.

        This method should:
        - Clean up all LVGL objects
        - Release any resources
        - Save state if needed
        """
        pass
