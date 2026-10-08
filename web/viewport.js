/* 화면 높이에 맞춰 작업 영역과 목록을 페이지로 나눈다. DOM과 선택 상태는 보존한다. */
const viewportPages = new WeakMap();
const viewportPartitions = new WeakMap();
let viewportFrame = 0;

function showViewportWorkspaceFor(element) {
  const workspace = element?.closest('.viewport-workspace');
  const panel = workspace?.closest('.panel');
  const select = panel?.querySelector('.viewport-toolbar select');
  if (!select) return;
  select.value = String([...panel.querySelectorAll('.viewport-workspace')].indexOf(workspace));
  select.dispatchEvent(new Event('change'));
}

function viewportPager(host) {
  let pager = host.querySelector(':scope > .viewport-pager');
  if (pager) return pager;
  pager = document.createElement('nav');
  pager.className = 'viewport-pager';
  pager.setAttribute('aria-label', '목록 페이지');
  pager.innerHTML = '<button type="button" class="btn sm">이전</button>'
    + '<span role="status" aria-live="polite"></span>'
    + '<button type="button" class="btn sm">다음</button>';
  host.append(pager);
  const buttons = pager.querySelectorAll('button');
  buttons.forEach((button, index) => button.addEventListener('click', () => {
    viewportPages.set(host, (viewportPages.get(host) || 0) + (index ? 1 : -1));
    scheduleViewport();
  }));
  return pager;
}

function viewportItems(host) {
  if (host.matches('.file-list')) {
    return [...host.querySelectorAll('.file-group-head, .file-row, .youtube-upload-file-row, .empty')]
      .filter(row => !row.closest('.file-group-children') || row.closest('.file-group.open'));
  }
  if (host.querySelector('.job-row')) return [...host.querySelectorAll('.job-row:not(.head)')];
  if (host.querySelector('.channel-list, .recent-list')) {
    return [...host.querySelector('.channel-list, .recent-list').children];
  }
  return [...host.children].filter(row => !row.matches('.viewport-pager'));
}

function paginateViewport(host) {
  if (!host.getClientRects().length) return;
  const pager = viewportPager(host);
  const items = viewportItems(host);
  host.classList.add('viewport-paged');
  items.forEach(item => item.classList.remove('viewport-hidden'));
  pager.hidden = true;
  if (!items.length) return;
  const head = host.querySelector('.job-row.head');
  const style = getComputedStyle(host);
  const padding = parseFloat(style.paddingTop) + parseFloat(style.paddingBottom);
  const gap = parseFloat(style.rowGap) || 0;
  const heights = items.map(item => {
    const itemStyle = getComputedStyle(item);
    return item.getBoundingClientRect().height + parseFloat(itemStyle.marginTop)
      + parseFloat(itemStyle.marginBottom) + gap;
  });
  const available = host.clientHeight - padding - (head?.getBoundingClientRect().height || 0);
  if (heights.reduce((sum, height) => sum + height, 0) <= available + 1) {
    viewportPages.set(host, 0);
    viewportPartitions.set(host, [items]);
    return;
  }
  const capacity = Math.max(1, available - 44);
  const columns = host.matches('.palette-grid') ? getComputedStyle(host).gridTemplateColumns.split(' ').length : 1;
  const pages = [];
  let page = [];
  let used = 0;
  for (let index = 0; index < items.length; index += columns) {
    const row = items.slice(index, index + columns);
    const height = Math.max(...heights.slice(index, index + columns));
    if (page.length && used + height > capacity) {
      pages.push(page);
      page = [];
      used = 0;
    }
    page.push(...row);
    used += height;
  }
  if (page.length) pages.push(page);
  viewportPartitions.set(host, pages);
  const current = Math.max(0, Math.min(viewportPages.get(host) || 0, pages.length - 1));
  viewportPages.set(host, current);
  const visible = new Set(pages[current]);
  items.forEach(item => item.classList.toggle('viewport-hidden', !visible.has(item)));
  pager.hidden = false;
  pager.querySelector('span').textContent = `${current + 1} / ${pages.length}`;
  const buttons = pager.querySelectorAll('button');
  buttons[0].disabled = current === 0;
  buttons[1].disabled = current === pages.length - 1;
}

function scheduleViewport() {
  if (viewportFrame) return;
  viewportFrame = requestAnimationFrame(() => {
    viewportFrame = 0;
    document.querySelectorAll('.panel.active .viewport-workspace, .overlay.active .modal, .palette-overlay.active .palette-dialog')
      .forEach(workspace => {
        workspace.querySelectorAll('.file-list, .seq-list, .card-body.tight, .card-body.stack, #dl-step-result > .card-body, .youtube-selected-source-list, .palette-grid')
          .forEach(paginateViewport);
      });
  });
}

function initializeViewport() {
  document.querySelectorAll('.panel').forEach(panel => {
    const workspaces = [...panel.querySelectorAll(':scope > .card, :scope > .monitor-hero, :scope > .merge-grid > .card, :scope > .youtube-upload-grid > .card')];
    const toolbar = document.createElement('div');
    toolbar.className = 'viewport-toolbar';
    const label = document.createElement('label');
    label.textContent = '작업 영역';
    const select = document.createElement('select');
    select.className = 'select';
    select.setAttribute('aria-label', '작업 영역');
    label.append(select);
    toolbar.append(label);
    const previous = document.createElement('button');
    const next = document.createElement('button');
    [previous, next].forEach((button, index) => {
      button.type = 'button';
      button.className = 'btn sm';
      button.textContent = index ? '다음 영역 →' : '← 이전 영역';
      toolbar.append(button);
      button.addEventListener('click', () => {
        const options = [...select.options].filter(option => !option.hidden);
        const current = options.findIndex(option => option.value === select.value);
        select.value = options[current + (index ? 1 : -1)].value;
        show();
      });
    });
    panel.prepend(toolbar);
    workspaces.forEach((workspace, index) => {
      workspace.classList.add('viewport-workspace');
      const title = workspace.querySelector('.card-title, .dl-loader-msg, .dl-finished-title')?.textContent || '감시 상태';
      const option = new Option(title, String(index));
      select.add(option);
    });
    // 업로드 첫 화면은 영상 선택, 다운로드 첫 화면은 주소 입력이다.
    select.value = panel.id === 'panel-youtube-upload' ? '1' : '0';
    const show = () => {
      const available = workspaces.map((workspace, index) => ({ workspace, index }))
        .filter(({ workspace }) => workspace.style.display !== 'none');
      [...select.options].forEach((option, index) => {
        option.hidden = workspaces[index].style.display === 'none';
      });
      if (!available.some(({ index }) => String(index) === select.value)) {
        select.value = String(available[0]?.index || 0);
      }
      workspaces.forEach((workspace, index) => {
        workspace.classList.toggle('viewport-current', String(index) === select.value);
      });
      previous.disabled = available[0]?.index === Number(select.value);
      next.disabled = available.at(-1)?.index === Number(select.value);
      previous.hidden = next.hidden = available.length <= 1;
      scheduleViewport();
    };
    select.addEventListener('change', show);
    const observer = new MutationObserver(records => {
      const newlyVisible = records.find(record => record.target.style.display !== 'none');
      if (newlyVisible && panel.id === 'panel-download') {
        select.value = String(workspaces.indexOf(newlyVisible.target));
      }
      show();
    });
    workspaces.forEach(workspace => observer.observe(workspace, { attributes: true, attributeFilter: ['style'] }));
    show();
    // 숨겨진 필수 입력도 해당 작업 영역을 열어 검증 메시지를 표시한다.
    panel.addEventListener('invalid', event => {
      const index = workspaces.indexOf(event.target.closest('.viewport-workspace'));
      if (index >= 0) {
        select.value = String(index);
        show();
        const host = event.target.closest('.viewport-paged');
        if (host) {
          paginateViewport(host);
          const page = (viewportPartitions.get(host) || []).findIndex(items => items.some(row => row.contains(event.target)));
          viewportPages.set(host, Math.max(0, page));
          paginateViewport(host);
        }
      }
    }, true);
  });
  const sidebar = document.querySelector('.sidebar');
  const system = document.querySelector('.syspanel');
  const systemButton = document.createElement('button');
  systemButton.className = 'btn viewport-system-button';
  systemButton.type = 'button';
  systemButton.textContent = '시스템 상태';
  systemButton.setAttribute('aria-expanded', 'false');
  sidebar.insertBefore(systemButton, system);
  systemButton.addEventListener('click', () => {
    const open = sidebar.classList.toggle('viewport-system-open');
    systemButton.setAttribute('aria-expanded', String(open));
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      sidebar.classList.remove('viewport-system-open');
      systemButton.setAttribute('aria-expanded', 'false');
    }
  });
  const menu = document.createElement('select');
  menu.className = 'select viewport-menu';
  menu.setAttribute('aria-label', '작업 메뉴');
  document.querySelectorAll('.nav-btn').forEach(button => menu.add(new Option(button.querySelector('span')?.textContent, button.dataset.tab)));
  menu.value = state.activeTab;
  menu.addEventListener('change', () => switchTab(menu.value));
  sidebar.prepend(menu);
  const onChanges = records => {
    const changed = records.some(record => {
      if (record.target.closest('.viewport-pager')) return false;
      if (record.type === 'attributes') {
        const clean = value => (value || '').replace(/\bviewport-[\w-]+\b/g, '').trim();
        return clean(record.oldValue) !== clean(record.target.className);
      }
      return true;
    });
    if (!changed) return;
    menu.value = state.activeTab;
    scheduleViewport();
  };
  ['.content', '.overlay'].forEach(selector => document.querySelectorAll(selector).forEach(root => {
    new MutationObserver(onChanges).observe(root, { childList: true, subtree: true, attributes: true, attributeOldValue: true, attributeFilter: ['class'] });
  }));
  window.addEventListener('resize', scheduleViewport);
  document.addEventListener('toggle', scheduleViewport, true);
  document.fonts.ready.then(scheduleViewport);
  scheduleViewport();
}
