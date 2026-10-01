import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { parse } from '@vue/compiler-dom'
import { compileScript, parse as parseSfc } from '@vue/compiler-sfc'
import { parse as parseJavaScript } from '@babel/parser'
import { computed, reactive, ref, shallowReadonly } from 'vue'

const source = (name) => readFileSync(new URL(`../src/components/${name}.vue`, import.meta.url), 'utf8')
const template = (name) => {
  const text = source(name)
  return parse(text.slice(text.indexOf('<template>') + 10, text.lastIndexOf('</template>')))
}
function elements(node) {
  return [...(node.type === 1 ? [node] : []), ...(node.children || []).flatMap(elements)]
}
const dashboardComponentNames = [
  'PublicWelcome', 'NotificationPreviewDialog', 'MemberBookingsView',
  'AvailabilityView', 'PaymentSettingsView', 'NotificationSettingsView',
  'CostVerificationDialog', 'MonthlyInvoiceDetails'
]
// Follow extracted presentation components instead of dropping their checks.
// Parent component bindings are checked separately below; native controls keep
// the exact original handler/model/validation contract fingerprint.
function dashboardElements(node = template('Dashboard')) {
  if (dashboardComponentNames.includes(node.tag)) {
    return dashboardElements(template(`dashboard/${node.tag}`))
  }
  return [...(node.type === 1 ? [node] : []), ...(node.children || []).flatMap(dashboardElements)]
}
function attribute(node, name) {
  return node.props.find(p => p.type === 6 && p.name === name)?.value?.content
}

// Captured before the theme change. Protect existing handlers, models and
// validation while allowing layout, colour and decorative artwork edits.
// Intentional future interaction changes must update this reviewed baseline.
const interactionBaseline = {
  Register: '0b14e5624de7009b96972836b7280f291c446c787a3c2a524dbd4e85740a33e4',
  // Reviewed addition: reconnect and explicit session-reset buttons.
  Dashboard: 'a47bef0bd917a49d48f7c0b841081f5642706d729e81edb8d6267ac8d6b39911',
  Navbar: 'e44b2c04e66c4522497fe65fa745329efa23acdd3054241ff59686b2abdf4dbe'
}
for (const [name, expected] of Object.entries(interactionBaseline)) {
  test(`${name} preserves existing handlers, models and validation`, () => {
    const contract = []
    for (const node of name === 'Dashboard' ? dashboardElements() : elements(template(name))) {
      for (const prop of node.props) {
        if (prop.type === 7 && ['on', 'model'].includes(prop.name)) {
          contract.push([node.tag, prop.name, prop.arg?.content || '', prop.exp?.content || '', ...prop.modifiers.map(m => m.content || m)])
        }
        if (prop.type === 6 && ['required', 'min', 'max', 'minlength', 'maxlength', 'pattern', 'type', 'autocomplete', 'inputmode'].includes(prop.name)) {
          contract.push([node.tag, prop.name, prop.value?.content || ''])
        }
      }
    }
    contract.sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b)))
    assert.equal(createHash('sha256').update(JSON.stringify(contract)).digest('hex'), expected)
  })
}

test('auth fields have associated labels in every mode', () => {
  const nodes = elements(template('Register'))
  for (const id of ['auth-name', 'auth-email', 'auth-password', 'auth-code', 'auth-whatsapp']) {
    assert.ok(nodes.find(n => n.tag === 'input' && attribute(n, 'id') === id))
    assert.ok(nodes.find(n => n.tag === 'label' && attribute(n, 'for') === id))
  }
})

test('dashboard form controls have explicit names or enclosing labels', () => {
  function visit(node, inLabel = false) {
    if (dashboardComponentNames.includes(node.tag)) {
      visit(template(`dashboard/${node.tag}`), inLabel)
      return
    }
    if (['input', 'select', 'textarea'].includes(node.tag)) {
      assert.ok(inLabel || attribute(node, 'aria-label'), `unnamed ${node.tag}: ${node.loc.source}`)
    }
    for (const child of node.children || []) visit(child, inLabel || node.tag === 'label')
  }
  visit(template('Dashboard'))
})

test('welcome actions resolve to existing routes and icons remain decorative', () => {
  const router = readFileSync(new URL('../src/router/index.js', import.meta.url), 'utf8')
  for (const name of ['ArenaHero', 'Dashboard']) {
    const nodes = name === 'Dashboard' ? dashboardElements() : elements(template(name))
    for (const node of nodes.filter(n => n.tag === 'router-link')) {
      const to = attribute(node, 'to')
      if (to) assert.ok(router.includes(`path: '${to}'`), `unknown action destination: ${to}`)
      assert.ok(node.children.length, 'action needs an accessible label')
    }
  }
  for (const name of ['ArenaIcon', 'ArenaFeatureIcon']) {
    const icon = elements(template(name)).find(n => n.tag === 'svg')
    assert.equal(attribute(icon, 'aria-hidden'), 'true')
    assert.equal(attribute(icon, 'focusable'), 'false')
  }
})

function presentationComponent(name) {
  const { descriptor } = parseSfc(source(`dashboard/${name}`))
  const { content } = compileScript(descriptor, { id: name })
  // Execute only the local SFC's setup declaration, without DOM rendering or
  // fetching. Vue's compiler supplies the real props/model bridge behavior.
  const declaration = content.replace(/^import.*$/gm, '').replace('export default', 'return')
  return new Function('computed', 'ArenaIcon', 'TentativeIcon', 'ArenaHero', declaration)(computed, null, null, null)
}

test('extracted views receive the existing state and callbacks directly', () => {
  const nodes = elements(template('Dashboard'))
  const camelize = name => name.replace(/-([a-z])/g, (_, letter) => letter.toUpperCase())
  for (const name of dashboardComponentNames) {
    const node = nodes.find(n => n.tag === name)
    assert.ok(node, `${name} is missing from the dashboard`)
    const component = presentationComponent(name)
    for (const prop of Object.keys(component.props || {})) {
      const binding = node.props.find(p => p.type === 7 && ['bind', 'model'].includes(p.name) && camelize(p.arg?.content || '') === prop)
      assert.equal(binding?.exp?.content, prop, `${name}.${prop} must use the existing dashboard value`)
    }
    for (const event of component.emits || []) {
      const prop = event.replace('update:', '')
      assert.ok(node.props.find(p => p.type === 7 && p.name === 'model' && p.arg.content === prop), `${name}.${event} needs a parent model binding`)
    }
  }
})

for (const [name, initial, updated] of [
  ['newFamilyName', 'First player', 'Second player'],
  ['whatsappPollQuestion', 'Original question', 'Updated question'],
  ['whatsappPollDates', ['2026-10-01'], ['2026-10-02', '2026-10-03']]
]) {
  test(`availability ${name} edits update parent state without a separate draft`, () => {
    const parent = reactive({ [name]: initial })
    const events = []
    const component = presentationComponent('AvailabilityView')
    const bindings = component.setup(shallowReadonly(parent), {
      expose() {},
      emit(event, value) {
        events.push([event, value])
        parent[event.replace('update:', '')] = value
      }
    })
    assert.deepEqual(bindings[name].value, initial)
    bindings[name].value = updated
    assert.deepEqual(events, [[`update:${name}`, updated]])
    assert.deepEqual(parent[name], updated)
    assert.deepEqual(bindings[name].value, updated)
    parent[name] = initial
    assert.deepEqual(bindings[name].value, initial)
  })
}

test('shared controller preserves the original state, handlers and lifecycle', () => {
  const code = readFileSync(new URL('../src/components/dashboard/useDashboard.js', import.meta.url), 'utf8')
  const ast = parseJavaScript(code, { sourceType: 'module' })
  const controller = ast.program.body.find(n => n.type === 'ExportDefaultDeclaration').declaration
  const nonSemanticKeys = new Set(['start', 'end', 'loc', 'extra', 'leadingComments', 'trailingComments', 'innerComments'])
  const semanticBody = JSON.stringify(controller.body, (key, value) => nonSemanticKeys.has(key) ? undefined : value)
  // Captured from Dashboard.setup before extraction; comments and formatting
  // can change freely. Intentional behavior changes require baseline review.
  // Reviewed addition: WhatsApp reconnect/reset and connection refresh lifecycle.
  assert.equal(createHash('sha256').update(semanticBody).digest('hex'), 'a8a3cfcec975753c80be8f530728cf8d32d4666c6b41fa7d60a3fa9106ff1895')
})

test('WhatsApp reset requires confirmation and reconnect preserves the session', async () => {
  const code = readFileSync(new URL('../src/components/dashboard/useDashboard.js', import.meta.url), 'utf8')
    .replace(/^import .*$/gm, '').replace('export default', 'return').replace('import.meta.env.VITE_API_BASE', "''")
  const calls = []
  let confirmed = false, unmount
  const browser = { location: { origin: 'http://test' }, localStorage: { getItem: () => null },
    confirm: () => confirmed, clearInterval: () => {}, removeEventListener: () => {} }
  const mockFetch = async (url, options) => {
    calls.push({ url, options })
    return { ok: true, text: async () => JSON.stringify({ ready: false, state: 'qr_required', qr_image: 'new-qr' }) }
  }
  const dashboard = new Function('computed', 'ref', 'watch', 'onMounted', 'onBeforeUnmount', 'useRouter',
    'getSessionValue', 'hasAuthSession', 'clearAuthSession', 'setSessionValue', 'getAuthSessionVersion', 'window', 'fetch', code)(
    computed, ref, () => {}, () => {}, fn => { unmount = fn }, () => ({}),
    key => key === 'auth_token' ? 'admin-token' : '', () => true, () => {}, () => {}, () => 0, browser, mockFetch
  )({ initialView: 'system-checks' })
  dashboard.systemChecks.value = { whatsapp: { default_test_recipient: '+31612345678' } }
  await dashboard.reconnectWhatsApp(true)
  assert.equal(calls.length, 0)
  await dashboard.reconnectWhatsApp(false)
  assert.equal(JSON.parse(calls[0].options.body).reset_session, false)
  assert.equal(calls[0].options.headers.Authorization, 'Bearer admin-token')
  assert.equal(dashboard.systemChecks.value.whatsapp.qr_image, 'new-qr')
  assert.equal(dashboard.systemChecks.value.whatsapp.default_test_recipient, '+31612345678')
  confirmed = true
  await dashboard.reconnectWhatsApp(true)
  assert.equal(JSON.parse(calls[2].options.body).reset_session, true)
  assert.equal(dashboard.whatsappReconnecting.value, false)
  unmount()
})
