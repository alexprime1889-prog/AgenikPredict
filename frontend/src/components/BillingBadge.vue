<template>
  <div v-if="isAuthenticated" class="billing-badge" @click="showBillingPanel = !showBillingPanel">
    <span v-if="isTrialActive" class="badge trial">
      Trial: {{ trialDaysLeft }}d left
    </span>
    <span v-else class="badge balance" :class="{ low: balanceCents < 100 }">
      ${{ (balanceCents / 100).toFixed(2) }}
    </span>

    <!-- Dropdown panel -->
    <div v-if="showBillingPanel" class="billing-panel">
      <div class="panel-header">
        <span v-if="isTrialActive">Free Trial</span>
        <span v-else>Account Balance</span>
      </div>

      <div v-if="isTrialActive" class="trial-info">
        <p>{{ $t('billing.trialDaysLeft', { days: trialDaysLeft }) }}</p>
        <p class="trial-hint">Full access during trial</p>
      </div>

      <div v-else class="balance-info">
        <div class="balance-amount">${{ (balanceCents / 100).toFixed(2) }}</div>
        <button class="topup-btn" @click="openTopUp">
          {{ $t('billing.topUp') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import {
  isAuthenticated,
  isTrialActive,
  trialDaysLeft,
  balanceCents,
} from '../store/auth'
import { getBillingPrices, createCheckout } from '../api/billing'

const showBillingPanel = ref(false)

const openTopUp = async () => {
  try {
    const pricesRes = await getBillingPrices()
    const packs = pricesRes.data?.packs || []
    if (packs.length > 0) {
      // Default to $20 pack
      const pack = packs.find((p) => p.amount === 2000) || packs[0]
      const res = await createCheckout(pack.price_id)
      if (res.success) {
        window.location.href = res.data.checkout_url
      }
    }
  } catch (e) {
    console.error('Checkout error:', e)
  }
}
</script>

<style scoped>
.billing-badge {
  position: relative;
  cursor: pointer;
}

.badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 12px;
  border-radius: 16px;
  font-size: 12px;
  font-weight: 600;
}

.badge.trial {
  background: rgba(123, 45, 142, 0.2);
  color: #7b2d8e;
  border: 1px solid rgba(123, 45, 142, 0.3);
}

.badge.balance {
  background: rgba(39, 174, 96, 0.15);
  color: #27ae60;
  border: 1px solid rgba(39, 174, 96, 0.3);
}

.badge.balance.low {
  background: rgba(231, 76, 60, 0.15);
  color: #e74c3c;
  border: 1px solid rgba(231, 76, 60, 0.3);
}

.billing-panel {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 8px;
  width: 240px;
  background: #111;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  padding: 16px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
  z-index: 100;
}

.panel-header {
  font-size: 13px;
  font-weight: 600;
  color: #fff;
  margin-bottom: 12px;
}

.balance-amount {
  font-size: 24px;
  font-weight: 700;
  color: #27ae60;
  margin-bottom: 12px;
}

.topup-btn {
  width: 100%;
  padding: 8px;
  background: #7b2d8e;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}

.topup-btn:hover {
  background: #9b3db0;
}

.trial-info p {
  color: #aaa;
  font-size: 13px;
  margin: 4px 0;
}

.trial-hint {
  color: #666;
  font-size: 11px;
}
</style>
