// static/js/scripts.js

// セキュリティ機能
document.addEventListener('contextmenu', function(e) {
    e.preventDefault();
    // 右クリック禁止（開発者ツール防止）
});

// キーボードショートカットの制限
document.addEventListener('keydown', function(e) {
    // Ctrl+F (Cmd+F)禁止
    if ((e.ctrlKey || e.metaKey) && (e.key === 'f' || e.key === 'F')) {
        e.preventDefault();
        alert('Ctrl+Fは禁止だよ！');
    }
    
    // F12キー禁止（開発者ツール防止）
    if (e.key === 'F12') {
        e.preventDefault();
        alert('F12キーは使用できません！');
    }
    
    // Ctrl+Shift+I (Cmd+Option+I)禁止
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'I') {
        e.preventDefault();
        alert('開発者ツールは使用できません！');
    }
    
    // Ctrl+U (Cmd+Option+U)禁止（ソース表示防止）
    if ((e.ctrlKey || e.metaKey) && e.key === 'u') {
        e.preventDefault();
        alert('ソース表示は禁止です！');
    }
});

// 開発者ツール検出
(function() {
    let devtools = {open: false, orientation: null};
    const threshold = 160;
    
    setInterval(function() {
        if (window.outerHeight - window.innerHeight > threshold || 
            window.outerWidth - window.innerWidth > threshold) {
            if (!devtools.open) {
                devtools.open = true;
                console.clear();
                console.log('%c開発者ツールが検出されました！', 'color: red; font-size: 20px; font-weight: bold;');
                console.log('%cこのゲームでは開発者ツールの使用は禁止されています。', 'color: red; font-size: 16px;');
            }
        } else {
            devtools.open = false;
        }
    }, 500);
})();

// リンクのプリロード機能（強化版）
let preloadCache = new Map();
let preloadTimeout = null;
let preloadQueue = [];
let isPreloading = false;
let maxConcurrentPreloads = 3;
let activePreloads = 0;

// より積極的なプリロード戦略
document.addEventListener('mouseover', function(e) {
    const link = e.target.closest('a[href]');
    if (!link || !link.href) return;
    
    // Wikipedia内のリンクのみプリロード
    if (!link.href.includes('/game?page=')) return;
    
    // 既にプリロード済みの場合はスキップ
    if (preloadCache.has(link.href)) return;
    
    // 即座にプリロードを開始（デバウンスを短縮）
    clearTimeout(preloadTimeout);
    preloadTimeout = setTimeout(() => {
        preloadPage(link.href);
    }, 50); // 100ms → 50msに短縮
});

// ページ内の全てのリンクを事前にプリロード
function preloadVisibleLinks() {
    const links = document.querySelectorAll('a[href*="/game?page="]');
    const visibleLinks = Array.from(links).filter(link => {
        const rect = link.getBoundingClientRect();
        return rect.top < window.innerHeight && rect.bottom > 0;
    });
    
    // 見えているリンクを優先的にプリロード
    visibleLinks.slice(0, 5).forEach(link => {
        if (!preloadCache.has(link.href)) {
            preloadPage(link.href);
        }
    });
}

// ページ読み込み完了後に見えるリンクをプリロード
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(preloadVisibleLinks, 500);
});

// ページのプリロード関数（並列処理対応）
function preloadPage(url) {
    if (preloadCache.has(url)) return;
    
    // 同時プリロード数の制限
    if (activePreloads >= maxConcurrentPreloads) {
        preloadQueue.push(url);
        return;
    }
    
    activePreloads++;
    preloadCache.set(url, 'loading');
    
    // URLからパラメータを抽出
    const urlObj = new URL(url);
    const page = urlObj.searchParams.get('page');
    const clicks = urlObj.searchParams.get('clicks');
    const mytarget = urlObj.searchParams.get('mytarget');
    const difficulty = urlObj.searchParams.get('difficulty');
    const start_time = urlObj.searchParams.get('start_time');
    
    // 軽量なAPIエンドポイントを使用
    const apiUrl = `/game_data?page=${encodeURIComponent(page)}&clicks=${clicks}&mytarget=${encodeURIComponent(mytarget)}&difficulty=${difficulty}&start_time=${start_time}`;
    
    // fetchでページデータをプリロード（タイムアウト短縮）
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 2000); // 2秒でタイムアウト
    
    fetch(apiUrl, {
        method: 'GET',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json'
        },
        signal: controller.signal
    })
    .then(response => {
        clearTimeout(timeoutId);
        if (response.ok) {
            return response.json();
        } else {
            throw new Error(`HTTP ${response.status}`);
        }
    })
    .then(data => {
        if (data.status === 'success') {
            preloadCache.set(url, {
                status: 'loaded',
                data: data,
                timestamp: Date.now()
            });
            console.log('Page preloaded:', url);
        } else {
            preloadCache.delete(url);
        }
    })
    .catch(error => {
        clearTimeout(timeoutId);
        if (error.name !== 'AbortError') {
            console.warn('Preload failed:', url, error);
        }
        preloadCache.delete(url);
    })
    .finally(() => {
        activePreloads--;
        // キューに待機中のプリロードがあれば実行
        if (preloadQueue.length > 0) {
            const nextUrl = preloadQueue.shift();
            setTimeout(() => preloadPage(nextUrl), 100);
        }
    });
}

// リンククリック時の処理（最適化版）
document.addEventListener('click', function(e) {
    const link = e.target.closest('a[href]');
    if (!link || !link.href) return;
    
    // Wikipedia内のリンクのみ対象
    if (!link.href.includes('/game?page=')) return;
    
    // プリロード済みの場合は即座に遷移
    const cached = preloadCache.get(link.href);
    if (cached && cached.status === 'loaded') {
        // プリロード済みなので即座に遷移
        showLoadingIndicator();
        return;
    }
    
    // ローディング表示を追加
    showLoadingIndicator();
    
    // 通常の遷移
    window.location.href = link.href;
});

// ローディングインジケーターの表示
function showLoadingIndicator() {
    // 既存のローディングインジケーターを削除
    const existing = document.getElementById('loading-indicator');
    if (existing) {
        existing.remove();
    }
    
    // 新しいローディングインジケーターを作成
    const indicator = document.createElement('div');
    indicator.id = 'loading-indicator';
    indicator.innerHTML = `
        <div style="
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 3px;
            background: linear-gradient(90deg, #007bff, #00d4ff);
            z-index: 9999;
            animation: loading 1s ease-in-out infinite;
        "></div>
        <style>
            @keyframes loading {
                0% { transform: translateX(-100%); }
                100% { transform: translateX(100%); }
            }
        </style>
    `;
    
    document.body.appendChild(indicator);
    
    // ページ遷移時に自動削除
    setTimeout(() => {
        if (indicator.parentNode) {
            indicator.remove();
        }
    }, 2000);
}


// Service Workerの登録（キャッシュ機能向上）
if ('serviceWorker' in navigator) {
    window.addEventListener('load', function() {
        navigator.serviceWorker.register('/sw.js')
            .then(function(registration) {
                console.log('ServiceWorker registration successful');
            })
            .catch(function(err) {
                console.log('ServiceWorker registration failed: ', err);
            });
    });
}

// ページの可視性変更時の最適化
document.addEventListener('visibilitychange', function() {
    if (document.hidden) {
        // ページが非表示の時にプリロードを一時停止
        clearTimeout(preloadTimeout);
    } else {
        // ページが表示された時にプリロードを再開
        console.log('Page visible, resuming preload operations');
    }
});

// ネットワーク状態の監視
if ('connection' in navigator) {
    navigator.connection.addEventListener('change', function() {
        const connection = navigator.connection;
        console.log('Connection changed:', connection.effectiveType);
        
        // 低速接続の場合はプリロードを制限
        if (connection.effectiveType === 'slow-2g' || connection.effectiveType === '2g') {
            console.log('Slow connection detected, limiting preload');
            // プリロードを無効化
            preloadCache.clear();
        }
    });
}
