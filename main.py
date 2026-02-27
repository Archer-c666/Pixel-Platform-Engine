from adventure.Adventure import Game

if __name__ == "__main__":
    try:
        Game().run()
    except Exception as e:
        print("运行错误:", e)
