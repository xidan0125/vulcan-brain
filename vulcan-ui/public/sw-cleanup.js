// 自动清除旧的 API 缓存
if ('caches' in self) {
  caches.keys().then(names => {
    names.forEach(name => {
      if (name.includes('api-cache')) {
        caches.delete(name);
        console.log('[SW Cleanup] Deleted cache:', name);
      }
    });
  });
}
