import logging
from synergesis.agents.core_agents import AgentContext, Aura

print('🌟 Starting Synergesis Agent Test...')

# Shared state
shared_state = {
    'glyph_bus': [],
    'current_time': 'test-time'
}

# Agent context
ctx = AgentContext(config={}, shared_state=shared_state)

# Initialize Aura
aura = Aura(ctx)
print('✅ Aura agent initialized!')

# Test emotional analysis
test_input = 'I am feeling excited and happy about this breakthrough!'
result = aura.perceive(test_input)
print(f'🧠 Aura perception result: {result}')

decision = aura.decide(result)
print(f'💭 Aura decision: {decision}')

if decision:
    action = aura.act(decision)
    print(f'⚡ Aura action result: {action}')

print(f'📊 Glyph bus contains: {len(shared_state["glyph_bus"])} glyphs')
print('🎉 Agent intelligence test completed!')
