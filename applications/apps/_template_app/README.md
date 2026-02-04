# Template App

This is a template for creating folder-based badge applications. This folder starts with an underscore so it won't be loaded by the app loader - it's just a template for you to copy.

## How to Use This Template

1. **Copy this entire folder**
   ```bash
   cp -r applications/apps/_template_app applications/apps/myapp
   ```

2. **Rename the main app file**
   ```bash
   cd applications/apps/myapp
   mv template_app_app.py myapp_app.py
   ```

3. **Update the code**
   - Change the class name from `TemplateApp` to `MyApp`
   - Update the app name in `__init__`
   - Implement your app logic in the `enter()` method

4. **Add resources** (optional)
   ```bash
   mkdir data assets
   # Add your data files, images, etc.
   ```

5. **Test your app**
   - Launch the badge launcher
   - Your app should appear in the Apps menu

## Folder Structure

```
myapp/
├── myapp_app.py          # Main app file (matches folder name)
├── data/                 # Optional: Data files
├── assets/               # Optional: Images, fonts, etc.
└── README.md             # App documentation
```

## Tips

- Keep the folder name simple and lowercase
- Name the main file `{foldername}_app.py`
- Use the `data/` or `assets/` subdirectories for resources
- Look at ChipTunez (`chiptunez/`) for a complete example
- Read `applications/README.md` for more details

## Example Apps

- **ChipTunez** - A complete app with JSON data files
- Check other apps in `applications/apps/` for more examples

## Need Help?

- See `applications/README.md` for full documentation
- Look at existing apps for examples
- The app loader automatically discovers your app - no config needed!
