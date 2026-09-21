import { expect, it } from 'vitest'
import { encode } from './geohash'

it('알려진 값과 일치 (위키백과 예시: 57.64911, 10.40744 → u4pruydqqvj)', () => {
  expect(encode(57.64911, 10.40744, 11)).toBe('u4pruydqqvj')
})
it('가까운 두 점은 앞자리가 같다', () => {
  expect(encode(37.5665, 126.978, 6)).toBe(encode(37.5666, 126.9781, 6))
})
