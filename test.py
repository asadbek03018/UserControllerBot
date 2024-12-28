import asyncio
from scripts import AdvertisementScheduler

scheduler = AdvertisementScheduler()

def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(scheduler.handle_advertisements())
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        scheduler.stop()
        loop.close()

if __name__ == "__main__":
    main()