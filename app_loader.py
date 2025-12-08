import os
import sys
import app

def load_categories(root_path="./applications"):
    """Scans for valid category directories."""
    cats = []
    print(f"Scanning {root_path} CWD: {os.getcwd()}")
    try:
        try:
            os.stat(root_path)
        except:
            print("Root path does not exist")
            return []
            
        for entry in os.listdir(root_path):
            print(f"Found entry: {entry}")
            if entry.startswith("."): continue
            
            # Check if directory
            try:
                st = os.stat(f"{root_path}/{entry}")
                print(f"Stat {entry}: {st}")
                if not st[0] & 0x4000:
                    print(f"Skipping {entry}, not a dir")
                    continue
            except Exception as e: 
                print(f"Stat error {entry}: {e}")
                continue
                
            cats.append(entry)
            print(f"Added category: {entry}")
    except Exception as e:
        print(f"Scan error: {e}")
        
    # Prioritize specific order if found
    ORDER = ["Apps", "Games", "Tools", "Settings"]
    cats.sort(key=lambda x: ORDER.index(x) if x in ORDER else 99)
    return cats

def load_apps_from_category(category_name):
    """Scans a category folder and imports app classes."""
    apps = []
    try:
        path = f"./applications/{category_name}"
        
        if path not in sys.path:
            sys.path.append(path)
            
        for entry in os.listdir(path):
            if entry.endswith(".py") and not entry.startswith("__"):
                mod_name = entry[:-3]
                try:
                    # Dynamic Import
                    mod = __import__(mod_name)
                    
                    # Scan for App subclasses
                    for attr_name in dir(mod):
                        attr = getattr(mod, attr_name)
                        try:
                            if issubclass(attr, app.App) and attr is not app.App:
                                # Instantiate
                                apps.append(attr())
                        except TypeError:
                            continue
                except Exception as e:
                    print(f"Failed to load {mod_name}: {e}")
    except Exception as e:
        print(f"Error loading category {category_name}: {e}")
        
    return apps
