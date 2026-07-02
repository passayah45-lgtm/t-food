from channels_redis.core import RedisChannelLayer
from redis.exceptions import TimeoutError as RedisTimeoutError


class TFoodRedisChannelLayer(RedisChannelLayer):
    async def _brpop_with_clean(self, index, channel, timeout):
        try:
            return await super()._brpop_with_clean(index, channel, timeout)
        except RedisTimeoutError:
            return None
