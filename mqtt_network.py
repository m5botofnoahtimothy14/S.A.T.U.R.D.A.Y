#!/usr/bin/env python3
import asyncio
from hbmqtt.broker import Broker

async def start_broker():
    config = {
        'listeners': {
            'default': {
                'type': 'tcp',
                'bind': '0.0.0.0:1883',
            },
            'ws': {
                'type': 'ws',
                'bind': '0.0.0.0:1884',
            }
        },
        'auth': {
            'allow-anonymous': True,
        }
    }
    broker = Broker(config)
    await broker.start()

if __name__ == '__main__':
    asyncio.run(start_broker())
