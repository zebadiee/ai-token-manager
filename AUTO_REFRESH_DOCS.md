# ⚡ Auto-Refresh Feature Documentation

## Overview

The AI Token Manager now includes a **non-blocking, background auto-refresh** system that keeps your data fresh without interrupting your workflow.

## Key Principles

### 1. **Non-Blocking** 🚫🛑
- Auto-refresh runs in a background thread
- Never blocks the UI or chat interface
- Your interactions always take priority
- Continues working even if refresh fails

### 2. **Incremental & Resilient** 📈
- If refresh fails, cached data remains available
- Network issues don't break your session
- Partial updates are preserved
- Graceful degradation on errors

### 3. **User Control** 🎮
- Manual "Refresh Models" button always available
- Can disable auto-refresh in Settings
- Configurable refresh intervals
- Override auto-refresh anytime

### 4. **Session Continuity** 🔄
- Active provider never changes mid-chat
- Ongoing conversations preserved
- Model selection persists
- Chat history maintained

### 5. **State Preservation** 💾
- Cached models kept until replaced
- Usage data updated incrementally
- Provider status preserved on failure
- No data loss on refresh timeout

### 6. **Passive Notifications** 🔔
- Subtle indicators show refresh status
- Non-intrusive warnings for outdated data
- Success confirmations are brief
- Never blocks user actions

## How It Works

### Background Thread
```python
# Runs in separate thread - never blocks UI
threading.Thread(
    target=token_manager.background_refresh_models,
    daemon=True
).start()
```

### Timeout Protection
```python
# 10-second timeout prevents hanging
with ThreadPoolExecutor(max_workers=1) as executor:
    future = executor.submit(self.get_all_models)
    models = future.result(timeout=10)
```

### Cache Fallback
```python
# Always returns data - cached if refresh fails
def background_refresh_models(self):
    try:
        # Try to refresh
        models = self.get_all_models()
        if models:
            self.cached_models = models  # Update cache
    except:
        pass  # Keep using cached data
    return self.cached_models or {}
```

## User Experience

### Visual Indicators

**Title Bar Indicators** (subtle, non-intrusive):
- 🔄 "Background refresh in progress..." - Refresh running
- ✓ "Auto-refreshed - models up to date" - Fresh data
- ⚠️ "Using cached models - refresh recommended" - Outdated cache

**Refresh Button** (dynamic labels):
- "🔄 Refresh Models" - No cache
- "🔄 Refresh (auto-updated)" - Fresh cache
- "🔄 Refresh (outdated)" - Stale cache

### Settings Control

**Enable/Disable Auto-Refresh**:
- Toggle in Settings tab
- Immediately starts/stops background refresh
- Saved in session state

**Refresh Interval**:
- 1 minute (testing)
- 3 minutes (active use)
- 5 minutes (default)
- 10 minutes (light use)
- 15 minutes (minimal use)

**Status Display**:
- Last refresh time
- Next refresh countdown
- Cache freshness indicator

## Behavior in Different Scenarios

### Normal Operation
1. App loads → Auto-refresh starts after interval
2. Background thread fetches models
3. Cache updates silently
4. UI shows "auto-updated" indicator
5. User continues working uninterrupted

### Network Failure
1. Refresh attempt fails
2. Cached models remain available
3. UI shows "cached models" warning
4. Manual refresh button still works
5. Next auto-refresh retries

### Timeout (Slow API)
1. Refresh hits 10-second timeout
2. Thread terminates gracefully
3. Cached data preserved
4. No error shown to user
5. Next interval tries again

### Provider Switch
1. User switches provider
2. Cached models still available
3. Background refresh continues
4. New provider models load
5. No interruption to workflow

### Mid-Chat
1. Refresh runs in background
2. Active chat continues
3. Provider stays same
4. Model selection preserved
5. History maintained

## Configuration

### Default Settings
```python
auto_refresh_enabled = True
auto_refresh_interval = 300  # 5 minutes
timeout = 10  # seconds
cache_max_age = 300  # 5 minutes for "fresh"
```

### Session State
```python
st.session_state.auto_refresh_enabled  # User toggle
st.session_state.last_interaction      # Track user activity
```

### Token Manager State
```python
self.cached_models = {}           # Cached model data
self.cache_timestamp = None       # When cache was updated
self.last_auto_refresh = None     # Last refresh time
self.refresh_in_progress = False  # Lock flag
```

## API Reference

### Methods

#### `should_auto_refresh() -> bool`
Non-blocking check if refresh should run.

**Returns**: `True` if refresh needed, `False` otherwise

**Checks**:
- Auto-refresh enabled
- Not already refreshing
- Interval elapsed

#### `background_refresh_models() -> Dict[str, List[Dict]]`
Background model refresh with timeout protection.

**Returns**: Model dict (cached on failure)

**Features**:
- 10-second timeout
- Exception handling
- Cache fallback
- Thread-safe

#### `get_cached_models() -> Tuple[Dict, bool]`
Get cached models with freshness indicator.

**Returns**: `(models_dict, is_fresh_bool)`

**Freshness**: `True` if < 5 minutes old

## Best Practices

### For Users
1. **Leave auto-refresh enabled** for best experience
2. **Manual refresh** when you need immediate update
3. **Check settings** if data seems outdated
4. **Don't disable** unless network is very slow

### For Developers
1. **Never block UI** in auto-refresh code
2. **Always timeout** long-running operations
3. **Preserve cache** on any failure
4. **Use threading** for background tasks
5. **Lock with flags** to prevent concurrent refreshes

## Troubleshooting

### Models not updating?
- Check Settings → Auto-refresh status
- Verify interval hasn't elapsed yet
- Try manual "Refresh Models"
- Check provider API key

### "Outdated" warning persists?
- Network may be slow
- Provider API may be down
- Increase refresh interval
- Use manual refresh

### Background refresh seems stuck?
- Has 10-second timeout
- Will auto-retry next interval
- Use manual refresh to force update
- Check console logs for errors

### Want faster updates?
- Reduce interval to 1-3 minutes
- Use manual refresh as needed
- Check if provider API has rate limits

## Advantages Over Other Approaches

### vs. Polling Every Request
- ✅ Reduced API calls
- ✅ No blocking on chat
- ✅ Better performance
- ✅ Cached fallback

### vs. Manual Only
- ✅ Always up-to-date
- ✅ Less user action needed
- ✅ Background convenience
- ✅ Still has manual option

### vs. Forced Refresh
- ✅ Never interrupts
- ✅ Preserves session
- ✅ No workflow disruption
- ✅ User stays in control

## Future Enhancements

Potential additions:
- Smart intervals based on usage patterns
- Provider-specific refresh rates
- Refresh on tab focus return
- Usage quota predictions
- Pre-emptive provider switching
- Activity-based refresh triggers

---

**Status**: ✅ Implemented and tested
**Type**: Non-blocking, background feature
**Impact**: Enhanced UX without workflow disruption
