'use client';

import { useState } from 'react';
import ShimmerButton from '@/components/ui/shimmer-button';
import { BorderBeam } from '@/components/ui/border-beam';
import AnimatedGradientText from '@/components/ui/animated-gradient';

export default function Page() {
  const [showTierInfo, setShowTierInfo] = useState(false);

  // Mock data
  const user = {
    credits: 2450,
    score_tier: 'BASED',
    score_multiplier: '1.20x',
    engaged_today: 12,
    available_posts: 8,
    current_streak: 5
  };

  const tierData = [
    { name: 'GOAT', minPoints: 1000, multiplier: '1.35x' },
    { name: 'OG', minPoints: 800, multiplier: '1.30x' },
    { name: 'Legend', minPoints: 600, multiplier: '1.25x' },
    { name: 'Based', minPoints: 400, multiplier: '1.20x' },
    { name: 'Degen', minPoints: 200, multiplier: '1.15x' },
    { name: 'Normie', minPoints: 100, multiplier: '1.10x' },
    { name: 'Anon', minPoints: 0, multiplier: '1.0x' },
  ];

  const weekDays = ['M', 'T', 'W', 'T', 'F', 'S', 'S'];
  const today = new Date().getDay();
  const todayMonBased = today === 0 ? 6 : today - 1;
  const daysEngaged = Math.min(user.current_streak, todayMonBased + 1);

  return (
    <div className="min-h-screen p-4 pb-20">
      {/* Balance Card */}
      <div className="relative overflow-hidden rounded-2xl glass-card p-6 mb-4">
        <BorderBeam size={300} duration={12} delay={0} />
        {/* Header Row */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center glass-icon-orange">
              <svg className="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 20 20">
                <path d="M4 4a2 2 0 00-2 2v1h16V6a2 2 0 00-2-2H4z"/>
                <path fillRule="evenodd" d="M18 9H2v5a2 2 0 002 2h12a2 2 0 002-2V9zM4 13a1 1 0 011-1h1a1 1 0 110 2H5a1 1 0 01-1-1zm5-1a1 1 0 100 2h1a1 1 0 100-2H9z" clipRule="evenodd"/>
              </svg>
            </div>
            <div>
              <p className="text-sm font-bold uppercase tracking-wider" style={{ color: '#f95400' }}>Balance</p>
              <p className="text-xs text-white font-semibold">{user.score_multiplier} multiplier</p>
            </div>
          </div>
          <div onClick={() => setShowTierInfo(true)} className="cursor-pointer tap-feedback">
            <div className="badge-glow px-4 py-2 rounded-full flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wide text-white">{user.score_tier}</span>
              <span className="text-[10px] font-bold text-white/80">ⓘ</span>
            </div>
          </div>
        </div>

        {/* Main Balance Display - High Contrast */}
        <div className="mb-6">
          <div className="flex items-baseline gap-2">
            <span className="text-6xl font-black tracking-tighter text-glow" style={{ color: '#f95400' }}>
              {user.credits.toLocaleString()}
            </span>
            <div className="flex items-center gap-1.5 mb-1">
              <svg className="w-5 h-5 text-white drop-shadow-lg" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M11.3 1.046A1 1 0 0112 2v5h4a1 1 0 01.82 1.573l-7 10A1 1 0 018 18v-5H4a1 1 0 01-.82-1.573l7-10a1 1 0 011.12-.38z" clipRule="evenodd"/>
              </svg>
              <span className="text-xl text-white font-medium">karma</span>
            </div>
          </div>
        </div>

        {/* Today's Progress - Gamified */}
        <div className="rounded-xl stat-card p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center glass-icon-orange">
                <svg className="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M11.3 1.046A1 1 0 0112 2v5h4a1 1 0 01.82 1.573l-7 10A1 1 0 018 18v-5H4a1 1 0 01-.82-1.573l7-10a1 1 0 011.12-.38z" clipRule="evenodd"/>
                </svg>
              </div>
              <span className="text-sm font-semibold text-white">Today's Progress</span>
            </div>
            <span className="text-sm font-mono font-bold text-white">
              {user.engaged_today}
              <span className="text-gray-400">/{user.engaged_today + user.available_posts}</span>
            </span>
          </div>
          <div className="h-3 bg-white/10 rounded-full overflow-hidden ring-1 ring-white/20">
            <div
              className="h-full progress-glow rounded-full transition-all duration-500"
              style={{ width: `${(user.engaged_today / (user.engaged_today + user.available_posts)) * 100}%` }}
            />
          </div>
          <p className="text-xs text-gray-300 font-medium mt-2">{user.available_posts} posts waiting for you</p>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <ShimmerButton
          className="h-auto w-full text-left flex flex-col items-start gap-2 p-4"
          shimmerColor="#ffffff"
          shimmerSize="0.1em"
          background="linear-gradient(135deg, #f95400 0%, #ff8c42 100%)"
          borderRadius="0.75rem"
        >
          <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-white/15 backdrop-blur-xl">
            <svg className="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M11.3 1.046A1 1 0 0112 2v5h4a1 1 0 01.82 1.573l-7 10A1 1 0 018 18v-5H4a1 1 0 01-.82-1.573l7-10a1 1 0 011.12-.38z" clipRule="evenodd"/>
            </svg>
          </div>
          <div>
            <p className="text-sm font-semibold text-white">Start Engaging</p>
            <p className="text-xs text-white/70">Earn karma now</p>
          </div>
        </ShimmerButton>
        <button className="group relative overflow-hidden rounded-xl stat-card p-4 text-left tap-feedback">
          <div className="absolute inset-0 bg-gradient-to-r from-transparent via-orange-500/10 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-700" />
          <div className="w-10 h-10 rounded-xl flex items-center justify-center mb-2 glass-icon">
            <svg className="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 20 20">
              <path d="M2 6a2 2 0 012-2h6a2 2 0 012 2v8a2 2 0 01-2 2H4a2 2 0 01-2-2V6zM14.553 7.106A1 1 0 0014 8v4a1 1 0 00.553.894l2 1A1 1 0 0018 13V7a1 1 0 00-1.447-.894l-2 1z"/>
            </svg>
          </div>
          <p className="text-sm font-bold text-white">Campaigns</p>
          <p className="text-xs text-gray-400 font-medium">Coming soon</p>
        </button>
      </div>

      {/* Daily Streaks */}
      <div className="relative overflow-hidden rounded-xl glass-card p-4">
        <BorderBeam size={250} duration={15} delay={3} />
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center glass-icon-orange">
            <svg className="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M12.395 2.553a1 1 0 00-1.45-.385c-.345.23-.614.558-.822.88-.214.33-.403.713-.57 1.116-.334.804-.614 1.768-.84 2.734a31.365 31.365 0 00-.613 3.58 2.64 2.64 0 01-.945-1.067c-.328-.68-.398-1.534-.398-2.654A1 1 0 005.05 6.05 6.981 6.981 0 003 11a7 7 0 1011.95-4.95c-.592-.591-.98-.985-1.348-1.467-.363-.476-.724-1.063-1.207-2.03zM12.12 15.12A3 3 0 017 13s.879.5 2.5.5c0-1 .5-4 1.25-4.5.5 1 .786 1.293 1.371 1.879A2.99 2.99 0 0113 13a2.99 2.99 0 01-.879 2.121z" clipRule="evenodd"/>
            </svg>
          </div>
          <div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-black text-white">{user.current_streak}</span>
              <span className="text-sm font-bold text-gray-300">day streak</span>
            </div>
          </div>
        </div>

        {/* Day Progress Pills */}
        <div className="flex gap-1.5">
          {weekDays.map((day, index) => {
            const isCompleted = index < daysEngaged;
            const isToday = index === todayMonBased;
            const isFuture = index > todayMonBased;

            return (
              <div key={index} className="flex-1 flex flex-col items-center gap-1.5">
                <div className={`w-full h-9 rounded-lg flex items-center justify-center transition-all ${
                  isCompleted
                    ? 'bg-gradient-to-b from-[#f95400] to-[#ff8c42] shadow-lg shadow-orange-500/30 ring-2 ring-orange-500/20'
                    : isToday
                    ? 'bg-orange-500/15 border-2 border-orange-500/50 border-dashed'
                    : isFuture
                    ? 'bg-white/5 border border-white/10'
                    : 'bg-white/10 border border-white/20'
                }`}>
                  {isCompleted && (
                    <svg className="w-4 h-4 text-white drop-shadow-lg" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/>
                    </svg>
                  )}
                </div>
                <span className={`text-[10px] font-bold ${
                  isCompleted ? 'text-orange-400' : isToday ? 'text-orange-300' : 'text-gray-400'
                }`}>
                  {day}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Floating Action Button */}
      <button className="fixed bottom-24 right-4 w-14 h-14 rounded-full glass-icon-orange float-animation glow-pulse shadow-lg tap-feedback z-40">
        <svg className="w-6 h-6 text-white mx-auto" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M11.3 1.046A1 1 0 0112 2v5h4a1 1 0 01.82 1.573l-7 10A1 1 0 018 18v-5H4a1 1 0 01-.82-1.573l7-10a1 1 0 011.12-.38z" clipRule="evenodd"/>
        </svg>
      </button>

      {/* Tier Info Modal */}
      {showTierInfo && (
        <div className="fixed inset-0 z-50 flex items-end justify-center p-4 pb-20">
          <div
            className="absolute inset-0 bg-black/70 backdrop-blur-md"
            onClick={() => setShowTierInfo(false)}
          />
          <div className="relative w-full max-w-sm rounded-2xl glass-elevated p-4 shadow-2xl">
            <BorderBeam size={200} duration={10} delay={1} />
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-base font-black text-white">Your Tier</h3>
              <button
                onClick={() => setShowTierInfo(false)}
                className="text-gray-400 hover:text-white font-bold text-lg transition-colors"
              >
                ✕
              </button>
            </div>
            <p className="text-sm text-gray-300 font-medium mb-4">
              You have <span className="text-[#f95400] font-black text-lg">{user.credits}</span> points on sorsa.io
            </p>
            <div className="space-y-2">
              {tierData.map((tier) => {
                const isCurrentTier = tier.name === user.score_tier;
                return (
                  <div
                    key={tier.name}
                    className={`flex items-center justify-between p-3 rounded-lg transition-all duration-200 ${
                      isCurrentTier ? 'tier-badge-active' : 'tier-badge hover:border-white/30'
                    }`}
                  >
                    <span className={`text-sm font-bold ${isCurrentTier ? 'text-white' : 'text-gray-200'}`}>
                      {tier.name}
                    </span>
                    <span className={`text-xs font-semibold ${isCurrentTier ? 'text-orange-200' : 'text-gray-400'}`}>
                      {tier.minPoints}+ pts
                    </span>
                    <span className={`text-sm font-mono font-bold ${isCurrentTier ? 'text-white' : 'text-gray-300'}`}>
                      {tier.multiplier}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
