// Service Worker for Wiki SixHop
const CACHE_NAME = 'wiki-sixhop-v1';
const STATIC_CACHE = 'static-v1';
const API_CACHE = 'api-v1';

// キャッシュするリソース
const STATIC_ASSETS = [
    '/',
    '/static/css/styles.css',
    '/static/js/scripts.js',
    'https://cdn.jsdelivr.net/npm/canvas-confetti@1.9.2/dist/confetti.browser.min.js',
    'https://fonts.googleapis.com/css2?family=Noto+Sans:wght@300;400;500;600;700&display=swap'
];

// インストール時の処理
self.addEventListener('install', function(event) {
    console.log('Service Worker installing...');
    event.waitUntil(
        caches.open(STATIC_CACHE)
            .then(function(cache) {
                console.log('Caching static assets');
                return cache.addAll(STATIC_ASSETS);
            })
            .then(function() {
                console.log('Service Worker installed');
                return self.skipWaiting();
            })
    );
});

// アクティベート時の処理
self.addEventListener('activate', function(event) {
    console.log('Service Worker activating...');
    event.waitUntil(
        caches.keys().then(function(cacheNames) {
            return Promise.all(
                cacheNames.map(function(cacheName) {
                    if (cacheName !== STATIC_CACHE && cacheName !== API_CACHE) {
                        console.log('Deleting old cache:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        }).then(function() {
            console.log('Service Worker activated');
            return self.clients.claim();
        })
    );
});

// フェッチ時の処理
self.addEventListener('fetch', function(event) {
    const request = event.request;
    const url = new URL(request.url);

    // 静的ファイルのキャッシュ戦略
    if (request.destination === 'style' || 
        request.destination === 'script' || 
        request.destination === 'image' ||
        url.pathname.startsWith('/static/')) {
        
        event.respondWith(
            caches.match(request)
                .then(function(response) {
                    if (response) {
                        return response;
                    }
                    return fetch(request).then(function(response) {
                        if (response.status === 200) {
                            const responseClone = response.clone();
                            caches.open(STATIC_CACHE).then(function(cache) {
                                cache.put(request, responseClone);
                            });
                        }
                        return response;
                    });
                })
        );
        return;
    }

    // APIエンドポイントのキャッシュ戦略
    if (url.pathname === '/game_data') {
        event.respondWith(
            caches.open(API_CACHE).then(function(cache) {
                return cache.match(request).then(function(response) {
                    if (response) {
                        // キャッシュから返すが、バックグラウンドで更新
                        fetch(request).then(function(fetchResponse) {
                            if (fetchResponse.status === 200) {
                                cache.put(request, fetchResponse.clone());
                            }
                        });
                        return response;
                    }
                    
                    // キャッシュにない場合はネットワークから取得
                    return fetch(request).then(function(fetchResponse) {
                        if (fetchResponse.status === 200) {
                            cache.put(request, fetchResponse.clone());
                        }
                        return fetchResponse;
                    });
                });
            })
        );
        return;
    }

    // その他のリクエストはネットワークファースト
    event.respondWith(
        fetch(request).catch(function() {
            return caches.match(request);
        })
    );
});

// メッセージ処理
self.addEventListener('message', function(event) {
    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
});
