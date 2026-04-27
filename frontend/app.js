const API = '/api/v1';

const state = {
    trends: [],
    posts: [],
    templates: [],
    selectedPostId: null,
    selectedTemplateIds: new Set(),
    pipelineResult: null,
    generatedImages: [],
    templateFilter: 'priority',
};

window.addEventListener('DOMContentLoaded', () => {
    loadStatus();
    loadTrends();
    loadPosts();
    loadScrapedTemplates();
});

async function refreshZoneA() {
    const btn = document.getElementById('btn-zone-a-refresh');
    if (btn) {
        btn.disabled = true;
        btn.textContent = 'Refreshing...';
    }

    try {
        await fetchJson(`${API}/refresh-sources`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ include_template_scrape: true }),
        });
    } catch (error) {
        console.error('Zone A refresh error:', error);
    }

    await Promise.all([
        loadStatus(),
        loadTrends(),
        loadPosts(),
        loadScrapedTemplates(),
    ]);

    if (btn) {
        btn.disabled = false;
        btn.textContent = 'Refresh';
    }
}

async function loadStatus() {
    try {
        const data = await fetchJson(`${API}/status`);
        const sources = data.sources || {};

        updateSourceBadge('src-linkedin', 'LinkedIn', sources.linkedin);
        updateSourceBadge('src-twitter', 'Twitter', sources.twitter);
        updateSourceBadge('src-devto', 'Dev.to', sources.devto);
        updateSourceBadge('src-reddit', 'Reddit', sources.reddit);
        updateSourceBadge('src-hashnode', 'Hashnode', sources.hashnode);
        updateSourceBadge('src-hackernews', 'HackerNews', sources.hackernews);
    } catch (error) {
        console.error('Status error:', error);
    }
}

function updateSourceBadge(id, label, info) {
    const el = document.getElementById(id);
    if (!el) return;

    const count = info?.count || 0;
    const isFresh = Boolean(info?.fresh);
    el.classList.remove('ok', 'empty');
    el.classList.add(count > 0 && isFresh ? 'ok' : 'empty');
    el.innerHTML = `<span class="dot"></span> ${label}: ${count}`;
}

async function loadTrends() {
    const btn = document.getElementById('btn-trends');
    const list = document.getElementById('trends-list');
    if (!btn || !list) return;

    btn.disabled = true;
    btn.textContent = 'Loading...';
    setPipeStep('ps-trends', 'active');

    try {
        const data = await fetchJson(`${API}/trends?limit=10`);
        state.trends = data.topics || [];
        renderQuickTrendChips();

        if (!state.trends.length) {
            list.innerHTML = '<p class="placeholder">No trending topics available yet.</p>';
        } else {
            const topicInput = document.getElementById('input-topic');
            if (topicInput && !topicInput.value.trim() && state.trends[0]?.title) {
                topicInput.value = state.trends[0].title;
            }

            list.innerHTML = state.trends.map((topic, idx) => {
                const title = esc((topic.title || '').slice(0, 120));
                const source = esc(topic.source || 'source');
                const score = Math.round(topic.score || 0);
                return `
                    <div class="list-item" data-topic-index="${idx}">
                        <span class="source hackernews">${source}</span>
                        ${title}
                        <span class="score">${score}</span>
                    </div>
                `;
            }).join('');

            list.querySelectorAll('[data-topic-index]').forEach((item) => {
                item.addEventListener('click', () => {
                    const idx = Number(item.getAttribute('data-topic-index'));
                    const picked = state.trends[idx];
                    if (picked?.title) {
                        document.getElementById('input-topic').value = picked.title;
                    }
                });
            });
        }

        setPipeStep('ps-trends', 'done');
    } catch (error) {
        list.innerHTML = `<p class="placeholder" style="color:#ef5350">${esc(error.message)}</p>`;
    } finally {
        btn.disabled = false;
        btn.textContent = 'Reload';
    }
}

function renderQuickTrendChips() {
    const host = document.getElementById('quick-trend-chips');
    if (!host) return;

    const top = state.trends.slice(0, 4);
    if (!top.length) {
        host.innerHTML = '';
        return;
    }

    host.innerHTML = top.map((topic, idx) =>
        `<button type="button" class="trend-chip-btn" onclick="pickTrend(${idx})">${esc((topic.title || '').slice(0, 36))}</button>`
    ).join('');
}

function pickTrend(index) {
    const topic = state.trends[index];
    if (!topic?.title) return;
    const topicInput = document.getElementById('input-topic');
    if (topicInput) {
        topicInput.value = topic.title;
    }
}

function useTopTrend() {
    if (!state.trends.length) {
        alert('Trends are still loading. Please click Reload in Trending Topics first.');
        return;
    }
    pickTrend(0);
}

async function loadPosts() {
    const btn = document.getElementById('btn-posts');
    const list = document.getElementById('posts-list');
    if (!btn || !list) return;

    btn.disabled = true;
    btn.textContent = 'Loading...';
    setPipeStep('ps-posts', 'active');

    try {
        const data = await fetchJson(`${API}/posts?limit=12`);
        state.posts = data.posts || [];

        if (!state.posts.length) {
            list.innerHTML = '<p class="placeholder">No real posts found yet.</p>';
        } else {
            list.innerHTML = state.posts.map((post, idx) => {
                const postId = esc(post.id || String(idx));
                const selected = state.selectedPostId === postId ? 'selected' : '';
                const sourceClass = sourceToClass(post.source);
                const source = esc(post.source || 'source');
                const title = esc((post.title || '').slice(0, 110));
                const engagement = Number(post.engagement || 0);
                const postUrl = post.url ? esc(post.url) : '';

                return `
                    <div class="list-item ${selected}" data-post-id="${postId}">
                        <span class="source ${sourceClass}">${source}</span>
                        ${title}
                        <span class="score">${engagement}</span>
                        ${postUrl ? `<a class="post-link" href="${postUrl}" target="_blank" rel="noopener">Open</a>` : ''}
                    </div>
                `;
            }).join('');

            list.querySelectorAll('[data-post-id]').forEach((item) => {
                item.addEventListener('click', (event) => {
                    if (event.target.classList.contains('post-link')) {
                        return;
                    }
                    const postId = item.getAttribute('data-post-id');
                    selectPost(postId);
                });
            });
        }

        setPipeStep('ps-posts', 'done');
    } catch (error) {
        list.innerHTML = `<p class="placeholder" style="color:#ef5350">${esc(error.message)}</p>`;
    } finally {
        btn.disabled = false;
        btn.textContent = 'Reload';
    }
}

function selectPost(postId) {
    state.selectedPostId = postId;

    const selected = state.posts.find((post, idx) => {
        const id = post.id || String(idx);
        return String(id) === String(postId);
    });

    if (selected?.title) {
        document.getElementById('input-topic').value = selected.title.slice(0, 220);
    }

    const list = document.getElementById('posts-list');
    if (list) {
        list.querySelectorAll('.list-item').forEach((item) => {
            item.classList.remove('selected');
            if (item.getAttribute('data-post-id') === String(postId)) {
                item.classList.add('selected');
            }
        });
    }
}

async function loadScrapedTemplates() {
    const btn = document.getElementById('btn-templates');
    const gallery = document.getElementById('template-gallery');
    if (!btn || !gallery) return;

    btn.disabled = true;
    btn.textContent = 'Loading...';

    try {
        const data = await fetchJson(`${API}/scraped-templates`);
        const templates = Array.isArray(data.templates) ? data.templates : [];
        const getSourcePriority = (sourceName) => {
            const src = String(sourceName || '').toLowerCase();
            if (src.includes('linkedin')) return 0;
            if (src.includes('twitter') || src.includes('x.com')) return 1;
            if (src.includes('reddit')) return 2;
            if (src.includes('dev.to') || src.includes('devto')) return 3;
            if (src.includes('hashnode')) return 4;
            if (src.includes('hackernews')) return 5;
            return 9;
        };
        const eduTerms = ['guide', 'learn', 'tutorial', 'how', 'tips', 'explained', 'roadmap', 'best practice'];

        state.templates = templates
            .map((template, idx) => ({ ...template, _uiId: String(template.id || `template_${idx}`) }))
            .sort((a, b) => {
                const aSrc = String(a.source || '').toLowerCase();
                const bSrc = String(b.source || '').toLowerCase();
                const ap = getSourcePriority(aSrc);
                const bp = getSourcePriority(bSrc);
                if (ap !== bp) return ap - bp;

                const aTitle = String(a.title || '').toLowerCase();
                const bTitle = String(b.title || '').toLowerCase();
                const aEdu = eduTerms.some((term) => aTitle.includes(term)) ? -1 : 0;
                const bEdu = eduTerms.some((term) => bTitle.includes(term)) ? -1 : 0;
                if (aEdu !== bEdu) return aEdu - bEdu;

                return bTitle.length - aTitle.length;
            });

        if (!state.templates.length) {
            gallery.innerHTML = '<p class="placeholder">No templates available yet.</p>';
            const stats = document.getElementById('templates-stats');
            if (stats) stats.textContent = 'Templates: 0';
            return;
        }

        renderTemplateGallery();
    } catch (error) {
        gallery.innerHTML = `<p class="placeholder" style="color:#ef5350">${esc(error.message)}</p>`;
    } finally {
        btn.disabled = false;
        btn.textContent = 'Reload Templates';
    }
}

function renderTemplateGallery() {
    const gallery = document.getElementById('template-gallery');
    if (!gallery) return;

    const templates = getFilteredTemplates();
    if (!templates.length) {
        gallery.innerHTML = '<p class="placeholder">No templates match this filter. Try All Sources.</p>';
        updateTemplateStats(0);
        updateSelectedTemplatesInfo();
        return;
    }

    gallery.innerHTML = templates.map((template) => {
        const id = String(template._uiId);
        const selected = state.selectedTemplateIds.has(id) ? 'selected' : '';
        const coverImage = template.coverImage || template.cover_image || '';
        const title = esc((template.title || 'Untitled').slice(0, 60));
        const source = esc(template.source || 'template');
        const sectionCount = Number(template.sectionCount || template.sections || 0) || '?';
        const style = esc(template.style || 'dark');
        const layout = esc(template.layout || template.layout_type || 'flow');
        const sourceUrlRaw = String(
            template.url ||
            template.source_url ||
            template.sourceUrl ||
            template.post_url ||
            template.postUrl ||
            template.permalink ||
            template.link ||
            ''
        ).trim();
        const sourceUrl = normalizeTemplateSourceUrl(sourceUrlRaw, template.source || '');

        return `
            <div class="template-card ${selected}" data-template-id="${esc(id)}">
                <div class="check-mark">Selected</div>
                ${coverImage
                    ? `<img src="${esc(coverImage)}" alt="${title}" loading="lazy" onerror="this.outerHTML='<div class=\"no-img\">${source}</div>'">`
                    : `<div class="no-img">${source}</div>`}
                <div class="template-info">
                    <div class="template-title">${title}</div>
                    <div class="template-meta">
                        <span>${source}</span>
                        <span>${sectionCount} sections</span>
                        <span>${style}</span>
                        <span>${layout}</span>
                    </div>
                    <div class="template-actions">
                        ${sourceUrl
                            ? `<a class="template-source-link" href="${esc(sourceUrl)}" target="_blank" rel="noopener" onclick="event.stopPropagation()">View Source</a>`
                            : '<span class="template-source-missing">No source link</span>'}
                    </div>
                </div>
            </div>
        `;
    }).join('');

    gallery.querySelectorAll('[data-template-id]').forEach((card) => {
        card.addEventListener('click', (event) => {
            if (event.target.closest('.template-source-link')) {
                return;
            }
            const id = card.getAttribute('data-template-id');
            toggleTemplate(id);
        });
    });

    updateTemplateStats(templates.length);
    updateSelectedTemplatesInfo();
}

function toggleTemplate(templateId) {
    if (state.selectedTemplateIds.has(templateId)) {
        state.selectedTemplateIds.delete(templateId);
    } else {
        state.selectedTemplateIds.add(templateId);
    }
    renderTemplateGallery();
}

function setTemplateFilter(filterName) {
    state.templateFilter = filterName;

    document.querySelectorAll('.template-filter-btn').forEach((button) => {
        button.classList.remove('active');
    });

    const active = document.getElementById(`filter-${filterName}`);
    if (active) {
        active.classList.add('active');
    }

    renderTemplateGallery();
}

function getFilteredTemplates() {
    const source = (template) => String(template.source || '').toLowerCase();

    if (state.templateFilter === 'linkedin') {
        return state.templates.filter((template) => source(template).includes('linkedin'));
    }

    if (state.templateFilter === 'twitter') {
        return state.templates.filter((template) => source(template).includes('twitter'));
    }

    if (state.templateFilter === 'priority') {
        const priority = state.templates.filter((template) => {
            const src = source(template);
            return src.includes('linkedin') || src.includes('twitter');
        });
        return priority.length ? priority : state.templates;
    }

    return state.templates;
}

function updateTemplateStats(filteredCount) {
    const stats = document.getElementById('templates-stats');
    if (!stats) return;

    stats.textContent = `Showing ${filteredCount} of ${state.templates.length} templates`;
}

function updateSelectedTemplatesInfo() {
    const info = document.getElementById('selected-templates-info');
    if (!info) return;

    info.textContent = `Selected templates: ${state.selectedTemplateIds.size}`;
}

async function runFullPipeline() {
    const topicInput = document.getElementById('input-topic');
    let topic = topicInput?.value?.trim() || '';
    const platform = document.getElementById('input-platform')?.value || 'linkedin';
    const outputChoice = getOutputChoice();
    const outputFormat = mapOutputChoice(outputChoice);
    const btn = document.getElementById('btn-generate');
    const progressArea = document.getElementById('progress-area');
    const progressSteps = document.getElementById('progress-steps');

    if (!topic && state.trends.length) {
        topic = state.trends[0].title || '';
        if (topicInput && topic) {
            topicInput.value = topic;
        }
    }

    if (!topic) {
        alert('Please enter a topic or choose a trending topic first.');
        return;
    }

    if (btn) {
        btn.disabled = true;
        btn.textContent = 'Running...';
    }

    resetPipelineBar();
    setPipeStep('ps-decide', 'active');

    if (progressArea) {
        progressArea.style.display = 'block';
    }
    if (progressSteps) {
        progressSteps.innerHTML = '<div class="prog-step running"><span class="prog-dot"></span>Pipeline started...</div>';
    }
    document.getElementById('results-area').style.display = 'none';

    try {
        const selectedTemplates = state.templates
            .filter((template) => state.selectedTemplateIds.has(String(template._uiId)))
            .map((template) => ({
                id: template.id,
                title: template.title,
                source: template.source,
                style: template.style || 'dark',
                layout: template.layout || template.layout_type || 'flow',
                sectionCount: template.sectionCount || template.sections || 0,
                url: template.url || '',
            }));

        const selectedPost = state.posts.find((post, idx) => String(post.id || String(idx)) === String(state.selectedPostId));

        const data = await fetchJson(`${API}/pipeline/full`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                topic,
                platform,
                output_format: outputFormat,
                include_ai_image: true,
                selected_templates: selectedTemplates,
                selected_post: selectedPost || null,
                tweaks: {},
            }),
        });

        state.pipelineResult = data;
        renderProgressSteps(data.steps || []);

        if (data.status !== 'complete') {
            throw new Error(data.error || 'Pipeline failed to complete');
        }

        renderResultPanel(data, outputChoice);
    } catch (error) {
        if (progressSteps) {
            progressSteps.innerHTML += `<div class="prog-step error"><span class="prog-dot"></span>${esc(error.message)}</div>`;
        }
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = 'Run Full Pipeline';
        }
    }
}

function renderProgressSteps(steps) {
    const progressSteps = document.getElementById('progress-steps');
    if (!progressSteps) return;

    if (!steps.length) {
        progressSteps.innerHTML = '<div class="prog-step">No step data returned.</div>';
        return;
    }

    progressSteps.innerHTML = steps.map((step) => {
        const stateClass = step.status === 'done' ? 'done' : (step.status === 'error' ? 'error' : 'running');
        return `<div class="prog-step ${stateClass}"><span class="prog-dot"></span>[${esc(step.zone || '?')}] ${esc(step.step || 'step')} - ${esc(step.detail || '')}</div>`;
    }).join('');

    steps.forEach((step) => {
        if (step.zone === 'B' && step.status === 'done') {
            setPipeStep('ps-decide', 'done');
        }
        if (step.zone === 'C' && step.status === 'done') {
            setPipeStep('ps-content', 'done');
        }
        if (step.zone === 'D' && String(step.step || '').includes('HTML') && step.status === 'done') {
            setPipeStep('ps-html', 'done');
        }
        if (step.zone === 'D' && String(step.step || '').includes('Frame') && step.status === 'done') {
            setPipeStep('ps-frames', 'done');
        }
        if (step.zone === 'E' && step.status === 'done') {
            setPipeStep('ps-ffmpeg', 'done');
        }
    });
}

function renderResultPanel(data, outputChoice) {
    const resultsArea = document.getElementById('results-area');
    const resultMeta = document.getElementById('result-meta');
    const resultPost = document.getElementById('result-post');
    const resultRaw = document.getElementById('result-raw');
    const imageElement = document.getElementById('result-image');
    const imageArea = document.getElementById('result-image-area');
    const htmlCard = document.getElementById('html-card');
    const tweakCard = document.getElementById('tweak-card');

    const content = data.content || {};
    const image = data.image || {};
    const exportData = data.export || {};

    const chips = [
        `content:${content.ai_provider || 'unknown'}`,
        `sections:${(content.sections || []).length}`,
        `category:${content.category || 'n/a'}`,
        `image:${image.provider || 'unknown'}`,
    ];
    if (data.html_generated_by) {
        chips.push(`html:${data.html_generated_by}`);
    }

    resultMeta.innerHTML = chips.map((chip) => `<span>${esc(chip)}</span>`).join('');
    resultPost.textContent = exportData.full_post_text || content.caption || 'No generated text available';
    resultRaw.textContent = JSON.stringify(data, null, 2);

    const imageUrl = image.image_url || '';
    if (imageUrl) {
        const absoluteImageUrl = toAbsoluteUrl(imageUrl);
        imageElement.src = withCacheBust(absoluteImageUrl);
        imageElement.style.display = 'block';
        addGeneratedImage(
            absoluteImageUrl,
            image.provider || 'cloudflare',
            content.title || data?.decision?.final_topic || 'Generated image'
        );
    } else {
        imageElement.removeAttribute('src');
        imageElement.style.display = 'none';
    }

    const animatedMode = outputChoice === 'gif';
    if (animatedMode) {
        if (tweakCard) tweakCard.style.display = 'block';
        if (htmlCard) htmlCard.style.display = 'block';
        fetchHtmlPreview(content, image);
    } else {
        if (tweakCard) tweakCard.style.display = 'none';
        if (htmlCard) htmlCard.style.display = 'none';
    }

    if (imageArea) {
        imageArea.style.display = imageUrl ? 'block' : 'none';
    }

    renderDownloadLinks(data, outputChoice);
    setPipeStep('ps-format', 'done');

    if (resultsArea) {
        resultsArea.style.display = 'block';
        resultsArea.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

function renderDownloadLinks(data, outputChoice) {
    const downloadFiles = document.getElementById('download-files');
    if (!downloadFiles) return;

    const links = [];
    const imageUrl = data?.image?.image_url || '';

    if (outputChoice === 'png' && imageUrl) {
        const pngDownloadUrl = withDownloadQuery(imageUrl);
        links.push(`<a class="btn-download" href="${esc(pngDownloadUrl)}" download="infographic_${Date.now()}.png">Download PNG</a>`);
    }

    const outputUrls = Array.isArray(data.output_urls) ? data.output_urls : [];
    const inferredUrls = Array.isArray(data.output_files)
        ? data.output_files.map((path) => `${API}/serve-file/${encodeURIComponent(basename(path))}`)
        : [];
    const allUrls = [...outputUrls, ...inferredUrls];

    const gifUrl = data.gif_url || allUrls.find((url) => url.toLowerCase().endsWith('.gif'));
    const staticPngUrl = allUrls.find((url) => url.toLowerCase().endsWith('.png'));

    if (gifUrl) {
        const gifDownloadUrl = withDownloadQuery(gifUrl);
        links.push(`<a class="btn-download" href="${esc(gifDownloadUrl)}" download="infographic_${Date.now()}.gif">Download GIF</a>`);
    }
    if (staticPngUrl && outputChoice !== 'png') {
        const staticDownloadUrl = withDownloadQuery(staticPngUrl);
        links.push(`<a class="btn-download" href="${esc(staticDownloadUrl)}" download="infographic_${Date.now()}.png">Download Static PNG</a>`);
    }

    if (data.html_path) {
        links.push('<button class="btn-download secondary" type="button" onclick="downloadHtmlFile()">Download HTML</button>');
    }

    links.push(`<a class="btn-download secondary" href="${API}/pipeline/download-zip" download="final_package.zip">Download ZIP</a>`);

    downloadFiles.innerHTML = links.join(' ');
}

function addGeneratedImage(imageUrl, provider, title) {
    const key = normalizeImageKey(imageUrl);
    if (!key) return;

    const normalized = {
        key,
        imageUrl: withCacheBust(toAbsoluteUrl(imageUrl)),
        provider: String(provider || 'cloudflare'),
        title: String(title || 'Generated image'),
        createdAt: Date.now(),
    };

    state.generatedImages = [
        normalized,
        ...state.generatedImages.filter((item) => item.key !== normalized.key),
    ].slice(0, 16);

    renderGeneratedImageHistory();
}

function renderGeneratedImageHistory() {
    const host = document.getElementById('result-image-history');
    if (!host) return;

    if (!state.generatedImages.length) {
        host.innerHTML = '<p class="placeholder">Generated images will appear here.</p>';
        return;
    }

    host.innerHTML = state.generatedImages.map((item, index) => {
        const safeTitle = esc(item.title);
        const safeProvider = esc(item.provider);
        const downloadUrl = withDownloadQuery(item.imageUrl);
        return `
            <a class="generated-image-card" href="${esc(downloadUrl)}" download="generated_${index + 1}.png" title="${safeTitle}">
                <img src="${esc(item.imageUrl)}" alt="${safeTitle}" loading="lazy">
                <span>${safeProvider}</span>
            </a>
        `;
    }).join('');
}

async function fetchHtmlPreview(content, image) {
    try {
        const platform = document.getElementById('input-platform')?.value || 'linkedin';
        const html = await fetchText(`${API}/pipeline/html-preview`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                content_data: content || {},
                image_url: toAbsoluteUrl(image?.image_url || ''),
                platform,
                tweaks: {},
            }),
        });

        const iframe = document.getElementById('html-preview');
        if (!iframe) return;

        iframe.srcdoc = html;

        const renderSizes = {
            linkedin: { width: 1200, height: 1500 },
            instagram: { width: 1080, height: 1080 },
            twitter: { width: 1200, height: 675 },
        };
        const fullSize = renderSizes[platform] || renderSizes.linkedin;
        const previewContainer = iframe.parentElement;

        const availableWidth = Math.max(320, (previewContainer?.clientWidth || 760) - 24);
        const availableHeight = Math.max(420, Math.min(window.innerHeight - 180, 820));
        const scale = Math.min(availableWidth / fullSize.width, availableHeight / fullSize.height, 1);

        iframe.style.width = `${fullSize.width}px`;
        iframe.style.height = `${fullSize.height}px`;
        iframe.style.transform = `scale(${scale})`;

        if (previewContainer) {
            previewContainer.style.minHeight = `${Math.ceil(fullSize.height * scale) + 24}px`;
        }
    } catch (error) {
        console.error('HTML preview error:', error);
    }
}

function downloadHtmlFile() {
    const iframe = document.getElementById('html-preview');
    const html = iframe?.srcdoc || '';
    if (!html) {
        alert('No HTML preview available yet.');
        return;
    }

    const blob = new Blob([html], { type: 'text/html' });
    const url = URL.createObjectURL(blob);

    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `infographic_${Date.now()}.html`;
    anchor.click();

    URL.revokeObjectURL(url);
}

async function applyTweaks() {
    if (!state.pipelineResult?.html_path) {
        alert('Generate animated output first, then apply tweaks.');
        return;
    }

    try {
        const tweaks = {
            bgColor: document.getElementById('tweak-bg')?.value || '#0a0a0a',
            accentColor: document.getElementById('tweak-accent')?.value || '#4fc3f7',
            textColor: document.getElementById('tweak-text')?.value || '#e8e8e8',
        };

        const title = (document.getElementById('tweak-title')?.value || '').trim();
        if (title) {
            tweaks.title = title;
        }

        const html = await fetchText(`${API}/pipeline/tweak`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ html_path: state.pipelineResult.html_path, tweaks }),
        });

        const iframe = document.getElementById('html-preview');
        if (iframe) {
            iframe.srcdoc = html;
        }
    } catch (error) {
        alert(`Tweak failed: ${error.message}`);
    }
}

function setPipeStep(id, stateClass) {
    const el = document.getElementById(id);
    if (!el) return;

    el.className = 'pipe-step';
    if (stateClass) {
        el.classList.add(stateClass);
    }
}

function resetPipelineBar() {
    [
        'ps-decide',
        'ps-content',
        'ps-html',
        'ps-frames',
        'ps-ffmpeg',
        'ps-format',
    ].forEach((stepId) => setPipeStep(stepId, ''));
}

function getOutputChoice() {
    return document.querySelector('input[name="output-format"]:checked')?.value || 'png';
}

function mapOutputChoice(choice) {
    return choice === 'png' ? 'image' : 'animated';
}

function sourceToClass(source) {
    const src = String(source || '').toLowerCase();
    if (src.includes('reddit')) return 'reddit';
    if (src.includes('dev') || src.includes('dev.to')) return 'devto';
    if (src.includes('hacker')) return 'hackernews';
    if (src.includes('hashnode')) return 'hashnode';
    if (src.includes('linkedin')) return 'linkedin';
    if (src.includes('twitter')) return 'twitter';
    return '';
}

function normalizeTemplateSourceUrl(url, sourceName = '') {
    const value = String(url || '').trim();
    if (!value) return '';

    const source = String(sourceName || '').toLowerCase();
    if (/^https?:\/\//i.test(value)) {
        return value;
    }
    if (value.startsWith('//')) {
        return `https:${value}`;
    }
    if (value.startsWith('www.')) {
        return `https://${value}`;
    }
    if (value.startsWith('/')) {
        return source.includes('reddit') ? `https://reddit.com${value}` : '';
    }
    if (source.includes('reddit') && value.startsWith('r/')) {
        return `https://reddit.com/${value}`;
    }

    return '';
}

function basename(path) {
    const normalized = String(path || '').replace(/\\/g, '/');
    const segments = normalized.split('/');
    return segments[segments.length - 1] || '';
}

async function fetchJson(url, options = {}) {
    const response = await fetch(url, options);
    if (!response.ok) {
        const message = await extractErrorMessage(response);
        throw new Error(message);
    }
    return response.json();
}

async function fetchText(url, options = {}) {
    const response = await fetch(url, options);
    if (!response.ok) {
        const message = await extractErrorMessage(response);
        throw new Error(message);
    }
    return response.text();
}

async function extractErrorMessage(response) {
    try {
        const body = await response.json();
        return body.detail || body.error || `Request failed (${response.status})`;
    } catch (_) {
        return `Request failed (${response.status})`;
    }
}

function esc(value) {
    return String(value || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function toAbsoluteUrl(url) {
    const value = String(url || '').trim();
    if (!value) return '';
    if (/^https?:\/\//i.test(value) || value.startsWith('data:')) {
        return value;
    }
    if (value.startsWith('/')) {
        return `${window.location.origin}${value}`;
    }
    return `${window.location.origin}/${value.replace(/^\/+/, '')}`;
}

function withDownloadQuery(url) {
    const absolute = toAbsoluteUrl(url);
    if (!absolute || absolute.startsWith('data:')) {
        return absolute;
    }
    try {
        const parsed = new URL(absolute);
        parsed.searchParams.set('download', '1');
        return parsed.toString();
    } catch (_) {
        return absolute;
    }
}

function withCacheBust(url) {
    const absolute = toAbsoluteUrl(url);
    if (!absolute || absolute.startsWith('data:')) {
        return absolute;
    }
    try {
        const parsed = new URL(absolute);
        parsed.searchParams.set('t', `${Date.now()}`);
        return parsed.toString();
    } catch (_) {
        return absolute;
    }
}

function normalizeImageKey(url) {
    const absolute = toAbsoluteUrl(url);
    if (!absolute) return '';
    return absolute.split('?')[0];
}
