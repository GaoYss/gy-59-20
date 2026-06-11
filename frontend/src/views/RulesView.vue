<script setup>
import { onMounted, reactive, ref } from 'vue'
import { AlertTriangle, Save } from 'lucide-vue-next'

import { ruleApi } from '../api/modules'
import EmptyState from '../components/EmptyState.vue'
import MessageBar from '../components/MessageBar.vue'

const rules = ref([])
const originalRules = ref([])
const savingId = ref(null)
const loadFailed = ref(false)
const message = reactive({ text: '', type: 'info' })

const confirmModal = reactive({
  open: false,
  loading: false,
  ruleId: null,
  subject: '',
  payload: null,
  impact: {
    affectedAppointments: 0,
    totalActiveAppointments: 0,
    weekendAppointments: 0,
    affectedDetails: []
  }
})

function syncOriginalRule(ruleId, serverData) {
  const fields = [
    'id', 'subject', 'minIntervalDays', 'maxDailySlots',
    'allowWeekend', 'passingScore', 'makeupWaitDays', 'enabled'
  ]
  const clean = {}
  for (const f of fields) {
    if (f in serverData) clean[f] = serverData[f]
  }
  const origIndex = originalRules.value.findIndex((r) => r.id === ruleId)
  if (origIndex >= 0) {
    originalRules.value[origIndex] = clean
  }
  const rulesIndex = rules.value.findIndex((r) => r.id === ruleId)
  if (rulesIndex >= 0) {
    rules.value[rulesIndex] = { ...rules.value[rulesIndex], ...clean }
  }
}

async function loadRules() {
  try {
    loadFailed.value = false
    const data = await ruleApi.list()
    rules.value = data
    originalRules.value = JSON.parse(JSON.stringify(data))
  } catch (error) {
    loadFailed.value = true
    message.text = '规则加载失败，请检查网络后刷新页面重试'
    message.type = 'error'
  }
}

function openWeekendConfirm(rule, finalPayload) {
  confirmModal.open = true
  confirmModal.loading = true
  confirmModal.ruleId = rule.id
  confirmModal.subject = rule.subject
  confirmModal.payload = finalPayload
  confirmModal.impact = {
    affectedAppointments: 0,
    totalActiveAppointments: 0,
    weekendAppointments: 0,
    affectedDetails: []
  }
  ruleApi.impactPreview(rule.id, false).then((impact) => {
    confirmModal.impact = impact
  }).catch(() => {
  }).finally(() => {
    confirmModal.loading = false
  })
}

function closeConfirmModal() {
  if (confirmModal.loading) return
  const rule = rules.value.find((r) => r.id === confirmModal.ruleId)
  const original = originalRules.value.find((r) => r.id === confirmModal.ruleId)
  if (rule && original) {
    rule.minIntervalDays = original.minIntervalDays
    rule.maxDailySlots = original.maxDailySlots
    rule.allowWeekend = original.allowWeekend
    rule.passingScore = original.passingScore
    rule.makeupWaitDays = original.makeupWaitDays
    rule.enabled = original.enabled
  }
  confirmModal.open = false
  confirmModal.ruleId = null
  confirmModal.payload = null
}

async function confirmAndSave() {
  if (!confirmModal.payload) return
  const payload = confirmModal.payload
  const ruleId = confirmModal.ruleId
  confirmModal.open = false
  confirmModal.ruleId = null
  confirmModal.payload = null
  await doSave(ruleId, payload)
}

async function doSave(ruleId, payload) {
  savingId.value = ruleId
  message.text = ''
  try {
    const updated = await ruleApi.update(ruleId, payload)
    syncOriginalRule(ruleId, updated)
    message.text = `${updated.subject} 规则已保存`
    message.type = 'success'
  } catch (error) {
    message.text = error.message
    message.type = 'error'
  } finally {
    savingId.value = null
  }
}

function saveRule(rule) {
  const originalRule = originalRules.value.find((r) => r.id === rule.id)
  const finalPayload = {
    minIntervalDays: rule.minIntervalDays,
    maxDailySlots: rule.maxDailySlots,
    allowWeekend: rule.allowWeekend,
    passingScore: rule.passingScore,
    makeupWaitDays: rule.makeupWaitDays,
    enabled: rule.enabled
  }
  const wasAllowed = originalRule ? originalRule.allowWeekend : true
  const nowDisallowed = rule.allowWeekend === false
  if (wasAllowed && nowDisallowed) {
    openWeekendConfirm(rule, finalPayload)
    return
  }
  doSave(rule.id, finalPayload)
}

onMounted(loadRules)
</script>

<template>
  <section class="panel">
    <div class="panel-heading">
      <div>
        <h3>约考规则设置</h3>
        <p>控制预约提前天数、每日名额、周末预约、合格线和补考等待期。</p>
      </div>
    </div>

    <MessageBar :message="message.text" :type="message.type" />

    <EmptyState
      v-if="loadFailed"
      title="规则加载失败"
      description="无法获取规则数据，请检查网络后刷新页面重试。"
    />
    <EmptyState
      v-else-if="rules.length === 0"
      title="暂无规则"
      description="后端初始化后会自动生成默认规则。"
    />

    <div v-if="!loadFailed && rules.length > 0" class="rule-grid">
      <article v-for="rule in rules" :key="rule.id" class="rule-card">
        <div class="rule-title">
          <h4>{{ rule.subject }}</h4>
          <label class="switch">
            <input v-model="rule.enabled" type="checkbox" />
            <span>开放预约</span>
          </label>
        </div>

        <div class="rule-fields">
          <label>
            <span>提前天数</span>
            <input v-model.number="rule.minIntervalDays" min="0" type="number" />
          </label>
          <label>
            <span>每日名额</span>
            <input v-model.number="rule.maxDailySlots" min="0" type="number" />
          </label>
          <label>
            <span>合格线</span>
            <input v-model.number="rule.passingScore" min="0" max="100" type="number" />
          </label>
          <label>
            <span>补考等待</span>
            <input v-model.number="rule.makeupWaitDays" min="0" type="number" />
          </label>
        </div>

        <label class="checkbox-row">
          <input v-model="rule.allowWeekend" type="checkbox" />
          <span>允许周末预约</span>
        </label>

        <button class="primary-button" :disabled="savingId === rule.id" type="button" @click="saveRule(rule)">
          <Save :size="18" />
          <span>{{ savingId === rule.id ? '保存中' : '保存规则' }}</span>
        </button>
      </article>
    </div>

    <div v-if="confirmModal.open" class="modal-overlay" @click.self="closeConfirmModal">
      <div class="modal-card">
        <h4 style="display:flex;align-items:center;gap:10px">
          <AlertTriangle :size="22" color="#b42318" />
          关闭周末预约确认
        </h4>
        <p>您即将为「{{ confirmModal.subject }}」关闭周末预约，以下是此次变更的影响分析：</p>

        <div v-if="confirmModal.loading" class="impact-summary">
          <span>正在统计受影响预约...</span>
        </div>

        <template v-else>
          <div class="impact-summary">
            <div>
              当前共有 <strong>{{ confirmModal.impact.totalActiveAppointments }}</strong> 个有效预约，
              其中周末预约 <strong>{{ confirmModal.impact.affectedAppointments }}</strong> 个。
            </div>
            <div style="margin-top:8px;font-size:13px;color:#8a5a00">
              这些预约均为规则变更前创建，变更后<b>不会被取消</b>，但之后的新预约将不再允许选择周末日期。
            </div>
          </div>

          <div v-if="confirmModal.impact.affectedDetails.length > 0" class="impact-detail-list">
            <table>
              <thead>
                <tr>
                  <th>学员</th>
                  <th>证件号</th>
                  <th>日期</th>
                  <th>时段</th>
                  <th>状态</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="d in confirmModal.impact.affectedDetails" :key="d.id">
                  <td>{{ d.studentName }}</td>
                  <td>{{ d.idNumber }}</td>
                  <td>{{ d.examDate }}</td>
                  <td>{{ d.timeslot }}</td>
                  <td>{{ d.status }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>

        <div class="modal-actions">
          <button class="secondary-button" type="button" :disabled="confirmModal.loading" @click="closeConfirmModal">
            取消
          </button>
          <button class="danger-button" type="button" :disabled="confirmModal.loading" @click="confirmAndSave">
            确认关闭周末预约
          </button>
        </div>
      </div>
    </div>
  </section>
</template>
