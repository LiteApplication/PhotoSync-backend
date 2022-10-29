import os
import re


class ConfigFile:
    DEFAULT = {
        "storage": "/srv/photosync",
        "index": "/srv/photosync/index.json",
        "address": "0.0.0.0",
        "port": "8080",
    }
    TYPES = {
        "storage": str,
        "address": str,
        "index": str,
        "port": int,
    }
    __all__ = ['storage', 'address', 'port']
    def __new__(cls, *args, **qwargs):
        if not hasattr(cls, 'instance'):
            cls.instance = super(ConfigFile, cls).__new__(cls)
            cls.instance.init(*args, **qwargs)
        return cls.instance

    def init(self, file_name: str):
        self.file_name = file_name
        self.config = dict()
        self.check_config()
        self.load_config()

    def load_config(self, name = None):
        if name is None:
            name = self.file_name
        print("Loading config ...")
        with open(name, "r") as f:
            for line in f.readlines():
                match line.replace("=", " = ", 1).split():
                    case ('#', *comment):
                        #print("Comment : ", " ".join(comment))
                        pass
                    case (name, "=", value):
                        if "${" in value:
                            # Replace ${variable} with previously defined variable
                            try:
                                value = re.sub(r'\${(.*)}', lambda m: self.config[m.group(1)], value)
                            except KeyError:
                                print(f"Error : Invalid variable in line {line}. Currently defined variables : {self.config.keys()}")
                        if name in self.config:
                            print(f"WARNING : {name} is already defined as {self.config[name]}, redefining as {value}")
                        if name in self.TYPES:
                            self.config[name] = self.TYPES[name](value)
                            print(f"Loaded {name}")
                        else:
                            print(f"WARNING : {name} is not a valid setting")
                            self.config[name] = value # Can still be used for other settings
                    case ():
                        pass
                    case _:
                        print("WARNING : Weird line :", line)
        print("Loaded config.")
    
    def check_config(self):
        if not os.path.exists(self.file_name):
            self.create_config(self.file_name)

    def create_config(self, name):
        print("Creating config file ...")
        with open(name, "x") as f: # Create and open the file for write
            lines = list()
            for name, value in self.DEFAULT.items():
                lines.append(f'{name}={value}')
                print(f"Saved {name}")
            f.write("\n".join(lines))
        print("Config created successfully. ")
    
    def __getattr__(self, name):
        if name in self.config:
            return self.config[name]
        elif name in self.DEFAULT:
            return self.TYPES[name](self.DEFAULT[name])
        else:
            raise AttributeError(f"ConfigFile has no attribute {name}")
        
    
    



