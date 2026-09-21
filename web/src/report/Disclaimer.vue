<script setup lang="ts">
// 화면 어디서든 결과 옆에 붙는 고지. 안전 판정을 단정하지 않는다.
</script>

<template>
  <aside class="disclaimer" role="note">
    <strong>이 결과는 전문가 진단이 아닙니다.</strong>
    측정값은 촬영 조건에 따라 달라질 수 있으며, 건물의 안전 여부를 판정하지 않습니다.
    표시는 <em>관찰 필요</em> 또는 <em>전문가 점검 권장</em>까지이며, 실제 판단은 전문가 점검으로 확인해야 합니다.
  </aside>
</template>

<style scoped>
.disclaimer {
  border-left: 3px solid #b45309;
  padding: 0.75rem 1rem;
  background: #fffbeb;
  font-size: 0.9rem;
  line-height: 1.6;
}
</style>
