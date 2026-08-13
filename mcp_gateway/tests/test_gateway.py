import json

import pytest
from mcp import Client
from mcp.client.subscriptions import ResourceUpdated as ClientResourceUpdated

from meme_games_mcp.client import Settings
from meme_games_mcp.server import build_gateway, current_token


URI = 'game://lobbies/room/agents/robot/state'


class FakeGameClient:
    def __init__(self): self.actions, self.presence_changes = [], []

    async def identity(self, token):
        if token != 'valid': raise RuntimeError('bad token')
        return {'lobby_id': 'room', 'agent_id': 'robot', 'name': 'Robot',
                'game': 'codenames', 'resource_uri': URI}

    async def state(self, token):
        await self.identity(token)
        return {'lobby_id': 'room', 'revision': 3, 'available_actions': ['join_team']}

    async def action(self, token, action, arguments=None):
        await self.identity(token)
        self.actions.append((action, arguments or {}))
        return {'ok': True, 'message': action, 'revision': 4}

    async def events(self):
        if False: yield None

    async def presence(self, token, connected):
        await self.identity(token)
        self.presence_changes.append(connected)

    async def close(self): pass


@pytest.mark.asyncio
async def test_tools_and_resource_use_the_same_agent_api():
    fake = FakeGameClient()
    _, mcp, _, _, _ = build_gateway(Settings('http://app', 'secret', ('testserver',), ()), fake)
    marker = current_token.set('valid')
    try:
        async with Client(mcp) as client:
            tools = await client.list_tools()
            assert {tool.name for tool in tools.tools} >= {
                'join_team', 'set_role', 'give_clue', 'reveal_card', 'end_turn', 'spectate'}
            contents = (await client.read_resource(URI)).contents[0]
            assert json.loads(contents.text)['revision'] == 3
            result = await client.call_tool('join_team', {'team': 'red'})
            assert result.structured_content['ok']
    finally: current_token.reset(marker)
    assert fake.actions == [('join_team', {'team': 'red'})]


@pytest.mark.asyncio
async def test_subscription_is_scoped_and_receives_resource_update():
    fake = FakeGameClient()
    _, mcp, _, _, bus = build_gateway(Settings('http://app', 'secret', ('testserver',), ()), fake)
    marker = current_token.set('valid')
    try:
        async with Client(mcp) as client:
            async with client.listen(resource_subscriptions=[URI]) as subscription:
                from mcp.server.subscriptions import ResourceUpdated
                await bus.publish(ResourceUpdated(uri=URI))
                event = await anext(subscription.__aiter__())
                assert isinstance(event, ClientResourceUpdated)
                assert event.uri == URI
    finally: current_token.reset(marker)
    assert fake.presence_changes == [True, False]
