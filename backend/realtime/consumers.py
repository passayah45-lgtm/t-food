from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth import get_user_model
from redis.exceptions import RedisError
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken

from operations_access.permissions import get_operations_actor


class OrdersConsumer(AsyncJsonWebsocketConsumer):
    close_code_unauthorized = 4401

    async def connect(self):
        self.groups_to_join = []
        self.user = await self.authenticate()
        if not self.user:
            await self.close(code=self.close_code_unauthorized)
            return

        self.groups_to_join = await self.group_names_for_user(self.user.id)
        for group_name in self.groups_to_join:
            await self.channel_layer.group_add(group_name, self.channel_name)

        await self.accept()
        await self.send_json({'type': 'connected'})

    async def disconnect(self, close_code):
        for group_name in getattr(self, 'groups_to_join', []):
            try:
                await self.channel_layer.group_discard(group_name, self.channel_name)
            except RedisError:
                pass

    async def receive_json(self, content, **kwargs):
        return None

    async def realtime_message(self, event):
        await self.send_json(event.get('payload', {}))

    async def authenticate(self):
        token = self.get_query_token()
        if not token:
            return None
        try:
            access_token = AccessToken(token)
            user_id = access_token['user_id']
        except (InvalidToken, TokenError, KeyError):
            return None
        return await self.get_user(user_id)

    def get_query_token(self):
        query_string = self.scope.get('query_string', b'').decode()
        values = parse_qs(query_string).get('token')
        return values[0] if values else ''

    @database_sync_to_async
    def get_user(self, user_id):
        User = get_user_model()
        try:
            return User.objects.get(id=user_id, is_active=True)
        except User.DoesNotExist:
            return None

    @database_sync_to_async
    def group_names_for_user(self, user_id):
        User = get_user_model()
        user = User.objects.get(id=user_id)
        groups = [f'user_{user.id}']
        if hasattr(user, 'merchant_profile'):
            groups.append(f'merchant_{user.id}')
        if hasattr(user, 'delivery_partner'):
            groups.append(f'partner_{user.id}')
            partner = user.delivery_partner
            if partner.is_verified and partner.is_available:
                groups.append('partners_available')
        actor = get_operations_actor(user)
        if actor.permissions and actor.is_global_scope:
            groups.append('operations')
            groups.append('operations_global')
        elif actor.permissions:
            groups.extend(f'operations_market_{market_id}' for market_id in actor.assigned_market_ids)
            groups.extend(f'operations_country_{code}' for code in actor.assigned_country_codes)
            groups.extend(f'operations_city_{city_id}' for city_id in actor.assigned_city_ids)
            groups.extend(f'operations_area_{area_id}' for area_id in actor.assigned_area_ids)
        return groups
