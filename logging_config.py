LOGGING_CONFIG_MAIN = { 
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": { 
        "standard": { 
            "format": "%(asctime)s | [%(levelname)s] | %(name)s - %(message)s"
        },
    },
    "handlers": { 
        "console": { 
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "level": "DEBUG",
            "stream": "ext://sys.stdout"  # Default is stderr
        },
        "main": { 
            "class": "logging.FileHandler",
            "filename": "",
            "formatter": "standard",
            "level": "INFO"
        },
        
    },
    "loggers": { 
        "main": { 
            "handlers": ["console", "main"],
            "level": "DEBUG",
        }
    } 
}

LOGGING_CONFIG_DEVICE_LOGGER = { 
    "device": { 
        "handlers": ["console", "main", "device"],
        "level": "DEBUG",
    }
}

LOGGING_CONFIG_DEVICE_HANDLER = { 
    "device": { 
        "class": "logging.FileHandler",
        "filename": "",
        "formatter": "standard",
        "level": "DEBUG"
    }
}
