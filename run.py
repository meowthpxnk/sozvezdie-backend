from app.startup import startup

if __name__ == "__main__":
    try:
        startup()
    except KeyboardInterrupt:
        print("Forced exit...")
    except Exception as err:
        print(err)
