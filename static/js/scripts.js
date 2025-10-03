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

// リンクのプリロード機能
let preloadCache = new Map();
let preloadTimeout = null;

// リンクにマウスオーバーした時にプリロード
document.addEventListener('mouseover', function(e) {
    const link = e.target.closest('a[href]');
    if (!link || !link.href) return;
    
    // Wikipedia内のリンクのみプリロード
    if (!link.href.includes('/game?page=')) return;
    
    // 既にプリロード済みの場合はスキップ
    if (preloadCache.has(link.href)) return;
    
    // デバウンス処理（連続したマウスオーバーを防ぐ）
    clearTimeout(preloadTimeout);
    preloadTimeout = setTimeout(() => {
        preloadPage(link.href);
    }, 100);
});

// ページのプリロード関数
function preloadPage(url) {
    if (preloadCache.has(url)) return;
    
    // プリロード中フラグを設定
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
    
    // fetchでページデータをプリロード
    fetch(apiUrl, {
        method: 'GET',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json'
        }
    })
    .then(response => {
        if (response.ok) {
            return response.json();
        } else {
            throw new Error(`HTTP ${response.status}`);
        }
    })
    .then(data => {
        if (data.status === 'success') {
            preloadCache.set(url, 'loaded');
            console.log('Page preloaded:', url);
        } else {
            preloadCache.delete(url);
        }
    })
    .catch(error => {
        console.warn('Preload failed:', url, error);
        preloadCache.delete(url);
    });
}

// リンククリック時の処理（ローディング表示なし）
document.addEventListener('click', function(e) {
    const link = e.target.closest('a[href]');
    if (!link || !link.href) return;
    
    // Wikipedia内のリンクのみ対象
    if (!link.href.includes('/game?page=')) return;
    
    // プリロード済みの場合は即座に遷移
    if (preloadCache.has(link.href) && preloadCache.get(link.href) === 'loaded') {
        // プリロード済みなので即座に遷移
        return;
    }
    
    // 通常の遷移（ローディング表示なし）
    window.location.href = link.href;
});


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
