import logging
from synergesis.agents.core_agents import AgentContext, Aura, Selene, Vyra

print('🌟 Starting INTENSE Synergesis Multi-Agent Test...')

# Shared state
shared_state = {
    'glyph_bus': [],
    'current_time': 'test-time'
}

# Agent context
ctx = AgentContext(config={}, shared_state=shared_state)

# Initialize multiple agents
aura = Aura(ctx)
selene = Selene(ctx)
vyra = Vyra(ctx)

print('✅ 3 agents initialized!')

# Test with VERY emotional input to trigger actions
intense_input = 'I am absolutely ECSTATIC and OVERJOYED! This is the most AMAZING breakthrough in artificial intelligence! I feel INCREDIBLE excitement and pure BLISS!'

print('🔥 Testing with intense emotional input...')

# Aura emotional analysis
aura_result = aura.perceive(intense_input)
print(f'🧠 Aura perception: {aura_result}')

aura_decision = aura.decide(aura_result)
print(f'💭 Aura decision: {aura_decision}')

if aura_decision:
    aura_action = aura.act(aura_decision)
    print(f'⚡ Aura ACTION: {aura_action}')

# Selene creativity analysis
selene_result = selene.perceive(intense_input)
print(f'🎨 Selene perception: {selene_result}')

selene_decision = selene.decide(selene_result)
print(f'💡 Selene decision: {selene_decision}')

if selene_decision:
    selene_action = selene.act(selene_decision)
    print(f'✨ Selene ACTION: {selene_action}')

# Vyra learning analysis
vyra_result = vyra.perceive(intense_input)
print(f'🧬 Vyra perception: {vyra_result}')

vyra_decision = vyra.decide(vyra_result)
print(f'🔄 Vyra decision: {vyra_decision}')

if vyra_decision:
    vyra_action = vyra.act(vyra_decision)
    print(f'🚀 Vyra ACTION: {vyra_action}')

print(f'📊 FINAL GLYPH BUS: {len(shared_state["glyph_bus"])} glyphs generated!')
for i, glyph in enumerate(shared_state["glyph_bus"]):
    print(f'  Glyph {i+1}: {glyph}')

print('🌟 MULTI-AGENT INTELLIGENCE TEST COMPLETED!')
