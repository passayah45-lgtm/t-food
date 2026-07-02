from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from fooddelivery.observability import get_health_snapshot


class HealthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []

    def get(self, request):
        include_optional = request.query_params.get('detail') in {'1', 'true', 'True'}
        snapshot = get_health_snapshot(include_optional=include_optional)
        return Response(snapshot)
