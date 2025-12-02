/**
 * DataTable - 可复用的数据表格组件
 * 
 * 功能：
 * - 分页（20/50/100）
 * - 排序（点击表头）
 * - 搜索（文本框）
 * - 筛选（下拉菜单）
 * - 全选/勾选
 * - 批量操作
 * 
 * 使用方法：
 * const table = new DataTable({
 *   containerId: 'tableContainer',
 *   columns: [
 *     { key: 'id', label: 'ID', sortable: true },
 *     { key: 'name', label: 'Name', sortable: true, searchable: true },
 *     { key: 'status', label: 'Status', filterable: true, filterOptions: ['Active', 'Inactive'] },
 *     { key: 'actions', label: 'Actions', render: (row) => `<button>Edit</button>` }
 *   ],
 *   pageSizes: [20, 50, 100],
 *   defaultPageSize: 20,
 *   selectable: true,            // 启用勾选
 *   idKey: 'id',                 // 行唯一标识字段
 *   batchActions: [              // 批量操作按钮
 *     { label: '批量删除', className: 'batch-btn-danger', onClick: (selectedRows) => {} }
 *   ],
 *   onRowClick: (row) => console.log('Clicked:', row)
 * });
 * table.setData(dataArray);
 * table.render();
 */
class DataTable {
  constructor(options) {
    this.containerId = options.containerId;
    this.columns = options.columns || [];
    this.pageSizes = options.pageSizes || [20, 50, 100];
    this.defaultPageSize = options.defaultPageSize || 20;
    this.onRowClick = options.onRowClick || null;
    this.emptyMessage = options.emptyMessage || '暂无数据';
    this.loadingMessage = options.loadingMessage || '加载中...';
    
    // 勾选功能
    this.selectable = options.selectable || false;
    this.idKey = options.idKey || 'id';
    this.batchActions = options.batchActions || [];
    
    // 搜索字段选择器功能
    this.searchFieldSelector = options.searchFieldSelector || false;
    
    // 筛选居中和标签
    this.filterCentered = options.filterCentered || false;
    this.filterLabelPrefix = options.filterLabelPrefix || '';
    
    // 状态
    this.data = [];
    this.filteredData = [];
    this.pageSize = this.defaultPageSize;
    this.currentPage = 1;
    this.sortColumn = null;
    this.sortDirection = 'asc';
    this.filters = {};
    this.searchKeyword = '';
    this.searchField = null; // 当前搜索的目标列（null 表示搜索所有可搜索列）
    
    // 选中状态
    this.selectedIds = new Set();
    
    // 初始化容器
    this.container = document.getElementById(this.containerId);
    if (!this.container) {
      console.error(`DataTable: Container #${this.containerId} not found`);
      return;
    }
  }
  
  /**
   * 设置数据
   */
  setData(data) {
    this.data = Array.isArray(data) ? data : [];
    this.currentPage = 1;
    // 清空选中状态
    this.selectedIds.clear();
    this._applyFiltersAndSort();
  }
  
  /**
   * 添加数据（追加模式）
   */
  appendData(newData) {
    if (Array.isArray(newData)) {
      this.data = this.data.concat(newData);
      this._applyFiltersAndSort();
    }
  }
  
  /**
   * 清空数据
   */
  clearData() {
    this.data = [];
    this.filteredData = [];
    this.currentPage = 1;
    this.selectedIds.clear();
  }
  
  /**
   * 应用筛选和排序
   */
  _applyFiltersAndSort() {
    let result = [...this.data];
    
    // 应用搜索
    if (this.searchKeyword) {
      const keyword = this.searchKeyword.toLowerCase();
      let searchableCols;
      
      // 如果指定了搜索字段，只搜索该字段
      if (this.searchField) {
        searchableCols = [this.searchField];
      } else {
        // 否则搜索所有可搜索列
        searchableCols = this.columns.filter(c => c.searchable).map(c => c.key);
      }
      
      result = result.filter(row => {
        return searchableCols.some(key => {
          const val = row[key];
          if (val == null) return false;
          return String(val).toLowerCase().includes(keyword);
        });
      });
    }
    
    // 应用筛选
    for (const [key, value] of Object.entries(this.filters)) {
      if (value && value !== '__all__') {
        result = result.filter(row => String(row[key]) === String(value));
      }
    }
    
    // 应用排序
    if (this.sortColumn) {
      result.sort((a, b) => {
        const valA = a[this.sortColumn];
        const valB = b[this.sortColumn];
        
        // 处理 null/undefined
        if (valA == null && valB == null) return 0;
        if (valA == null) return 1;
        if (valB == null) return -1;
        
        // 数值比较
        if (typeof valA === 'number' && typeof valB === 'number') {
          return this.sortDirection === 'asc' ? valA - valB : valB - valA;
        }
        
        // 字符串比较
        const strA = String(valA).toLowerCase();
        const strB = String(valB).toLowerCase();
        if (strA < strB) return this.sortDirection === 'asc' ? -1 : 1;
        if (strA > strB) return this.sortDirection === 'asc' ? 1 : -1;
        return 0;
      });
    }
    
    this.filteredData = result;
  }
  
  /**
   * 获取当前页数据
   */
  _getPageData() {
    const start = (this.currentPage - 1) * this.pageSize;
    const end = start + this.pageSize;
    return this.filteredData.slice(start, end);
  }
  
  /**
   * 获取总页数
   */
  _getTotalPages() {
    return Math.ceil(this.filteredData.length / this.pageSize) || 1;
  }
  
  /**
   * 设置搜索关键词
   */
  search(keyword) {
    this.searchKeyword = keyword;
    this.currentPage = 1;
    this._applyFiltersAndSort();
    this.render();
  }
  
  /**
   * 设置搜索字段
   * @param {string|null} key - 列键名，null 表示搜索所有可搜索列
   */
  setSearchField(key) {
    this.searchField = key;
    this.currentPage = 1;
    this._applyFiltersAndSort();
    this.render();
  }
  
  /**
   * 设置筛选条件
   */
  setFilter(key, value) {
    if (value === '__all__' || !value) {
      delete this.filters[key];
    } else {
      this.filters[key] = value;
    }
    this.currentPage = 1;
    this._applyFiltersAndSort();
    this.render();
  }
  
  /**
   * 设置排序
   */
  setSort(column) {
    if (this.sortColumn === column) {
      this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
      this.sortColumn = column;
      this.sortDirection = 'asc';
    }
    this._applyFiltersAndSort();
    this.render();
  }
  
  /**
   * 设置页大小
   */
  setPageSize(size) {
    this.pageSize = size;
    this.currentPage = 1;
    this.render();
  }
  
  /**
   * 跳转到指定页
   */
  goToPage(page) {
    const totalPages = this._getTotalPages();
    this.currentPage = Math.max(1, Math.min(page, totalPages));
    this.render();
  }
  
  /**
   * 获取选中的行数据
   */
  getSelectedRows() {
    return this.data.filter(row => this.selectedIds.has(String(row[this.idKey])));
  }
  
  /**
   * 获取选中的ID列表
   */
  getSelectedIds() {
    return Array.from(this.selectedIds);
  }
  
  /**
   * 清空选中
   */
  clearSelection() {
    this.selectedIds.clear();
    this.render();
  }
  
  /**
   * 全选当前页
   */
  selectAllOnPage() {
    const pageData = this._getPageData();
    pageData.forEach(row => {
      this.selectedIds.add(String(row[this.idKey]));
    });
    this.render();
  }
  
  /**
   * 取消选中当前页
   */
  deselectAllOnPage() {
    const pageData = this._getPageData();
    pageData.forEach(row => {
      this.selectedIds.delete(String(row[this.idKey]));
    });
    this.render();
  }
  
  /**
   * 全选所有数据
   */
  selectAll() {
    this.filteredData.forEach(row => {
      this.selectedIds.add(String(row[this.idKey]));
    });
    this.render();
  }
  
  /**
   * 切换行选中状态
   */
  toggleRowSelection(rowId) {
    const id = String(rowId);
    if (this.selectedIds.has(id)) {
      this.selectedIds.delete(id);
    } else {
      this.selectedIds.add(id);
    }
    this.render();
  }
  
  /**
   * 渲染表格
   */
  render() {
    if (!this.container) return;
    
    const pageData = this._getPageData();
    const totalPages = this._getTotalPages();
    const totalRecords = this.filteredData.length;
    const selectedCount = this.selectedIds.size;
    
    // 检查当前页是否全选
    const pageAllSelected = pageData.length > 0 && 
      pageData.every(row => this.selectedIds.has(String(row[this.idKey])));
    
    // 构建HTML
    let html = `
      <div class="data-table-wrapper">
        <!-- 工具栏 -->
        <div class="data-table-toolbar ${this.filterCentered ? 'toolbar-three-columns' : ''}">
          <div class="toolbar-left">
            <!-- 搜索字段选择器 -->
            ${this._renderSearchFieldSelector()}
            <!-- 搜索框 -->
            <input type="text" class="data-table-search" placeholder="${this._t('search_placeholder')}" value="${this._escapeHtml(this.searchKeyword)}">
            
            <!-- 筛选下拉（如果不居中则放在这里） -->
            ${!this.filterCentered ? this._renderFilters() : ''}
          </div>
          ${this.filterCentered ? `
          <div class="toolbar-center">
            <!-- 筛选下拉（居中显示） -->
            ${this._renderFilters()}
          </div>
          ` : ''}
          <div class="toolbar-right">
            <!-- 页大小选择 -->
            <label>${this._t('per_page')}
              <select class="data-table-pagesize">
                ${this.pageSizes.map(size => `<option value="${size}" ${size === this.pageSize ? 'selected' : ''}>${size}</option>`).join('')}
              </select>
            </label>
            <span class="data-table-info">${this._t('total')} ${totalRecords} ${this._t('records')}</span>
          </div>
        </div>
        
        <!-- 批量操作栏 -->
        ${this.selectable ? this._renderBatchBar(selectedCount) : ''}
        
        <!-- 表格 -->
        <table class="data-table">
          <thead>
            <tr>
              ${this.selectable ? `
                <th class="data-table-th data-table-checkbox-col">
                  <input type="checkbox" class="data-table-select-all" ${pageAllSelected ? 'checked' : ''}>
                </th>
              ` : ''}
              ${this.columns.map(col => this._renderHeaderCell(col)).join('')}
            </tr>
          </thead>
          <tbody>
            ${pageData.length > 0 ? pageData.map(row => this._renderRow(row)).join('') : `<tr><td colspan="${this.columns.length + (this.selectable ? 1 : 0)}" class="data-table-empty">${this.emptyMessage}</td></tr>`}
          </tbody>
        </table>
        
        <!-- 分页 -->
        ${this._renderPagination(totalPages)}
      </div>
    `;
    
    this.container.innerHTML = html;
    
    // 绑定事件
    this._bindEvents();
  }
  
  /**
   * 渲染批量操作栏
   */
  _renderBatchBar(selectedCount) {
    if (this.batchActions.length === 0) return '';
    
    const isVisible = selectedCount > 0;
    
    return `
      <div class="data-table-batch-bar ${isVisible ? 'visible' : ''}">
        <div class="batch-bar-left">
          <span class="selected-count">${this._t('selected')} <strong>${selectedCount}</strong> ${this._t('items')}</span>
          <button type="button" class="batch-clear-btn">${this._t('clear_selection')}</button>
        </div>
        <div class="batch-bar-right">
          ${this.batchActions.map((action, idx) => `
            <button type="button" class="batch-btn ${action.className || ''}" data-batch-action="${idx}">${action.label}</button>
          `).join('')}
        </div>
      </div>
    `;
  }
  
  /**
   * 渲染表头单元格
   */
  _renderHeaderCell(col) {
    let className = 'data-table-th';
    let sortIcon = '';
    
    if (col.sortable) {
      className += ' sortable';
      if (this.sortColumn === col.key) {
        sortIcon = this.sortDirection === 'asc' ? ' ▲' : ' ▼';
      }
    }
    
    return `<th class="${className}" data-column="${col.key}" data-sortable="${col.sortable || false}">${col.label}${sortIcon}</th>`;
  }
  
  /**
   * 渲染数据行
   */
  _renderRow(row) {
    const rowId = String(row[this.idKey] || '');
    const isSelected = this.selectedIds.has(rowId);
    
    let checkboxCell = '';
    if (this.selectable) {
      checkboxCell = `
        <td class="data-table-checkbox-col">
          <input type="checkbox" class="data-table-row-checkbox" data-row-id="${this._escapeHtml(rowId)}" ${isSelected ? 'checked' : ''}>
        </td>
      `;
    }
    
    const cells = this.columns.map(col => {
      let content;
      if (col.render && typeof col.render === 'function') {
        content = col.render(row);
      } else {
        content = row[col.key] != null ? this._escapeHtml(String(row[col.key])) : '';
      }
      return `<td>${content}</td>`;
    }).join('');
    
    return `<tr class="data-table-row ${isSelected ? 'selected' : ''}" data-row-id="${this._escapeHtml(rowId)}">${checkboxCell}${cells}</tr>`;
  }
  
  /**
   * 渲染搜索字段选择器
   */
  _renderSearchFieldSelector() {
    if (!this.searchFieldSelector) return '';
    
    const searchableCols = this.columns.filter(c => c.searchable);
    if (searchableCols.length === 0) return '';
    
    return `
      <select class="data-table-filter search-field-selector">
        <option value="__all__" ${!this.searchField ? 'selected' : ''}>${this._t('search_all_fields')}</option>
        ${searchableCols.map(col => `
          <option value="${col.key}" ${this.searchField === col.key ? 'selected' : ''}>${col.label}</option>
        `).join('')}
      </select>
    `;
  }
  
  /**
   * 渲染筛选下拉
   */
  _renderFilters() {
    const filterableCols = this.columns.filter(c => c.filterable && c.filterOptions);
    if (filterableCols.length === 0) return '';
    
    return filterableCols.map(col => {
      const currentValue = this.filters[col.key] || '__all__';
      const labelPrefix = this.filterLabelPrefix ? `<span class="filter-label">${this.filterLabelPrefix}</span>` : '';
      return `
        ${labelPrefix}
        <select class="data-table-filter" data-filter-key="${col.key}">
          <option value="__all__">${col.filterLabel || col.label} (${this._t('all')})</option>
          ${col.filterOptions.map(opt => {
            const optValue = typeof opt === 'object' ? opt.value : opt;
            const optLabel = typeof opt === 'object' ? opt.label : opt;
            return `<option value="${this._escapeHtml(String(optValue))}" ${String(currentValue) === String(optValue) ? 'selected' : ''}>${this._escapeHtml(String(optLabel))}</option>`;
          }).join('')}
        </select>
      `;
    }).join('');
  }
  
  /**
   * 渲染分页
   */
  _renderPagination(totalPages) {
    if (totalPages <= 1) return '';
    
    let pages = [];
    const maxVisible = 5;
    let start = Math.max(1, this.currentPage - Math.floor(maxVisible / 2));
    let end = Math.min(totalPages, start + maxVisible - 1);
    
    if (end - start < maxVisible - 1) {
      start = Math.max(1, end - maxVisible + 1);
    }
    
    // 首页
    if (start > 1) {
      pages.push(`<button class="page-btn" data-page="1">1</button>`);
      if (start > 2) {
        pages.push(`<span class="page-ellipsis">...</span>`);
      }
    }
    
    // 中间页码
    for (let i = start; i <= end; i++) {
      pages.push(`<button class="page-btn ${i === this.currentPage ? 'active' : ''}" data-page="${i}">${i}</button>`);
    }
    
    // 末页
    if (end < totalPages) {
      if (end < totalPages - 1) {
        pages.push(`<span class="page-ellipsis">...</span>`);
      }
      pages.push(`<button class="page-btn" data-page="${totalPages}">${totalPages}</button>`);
    }
    
    return `
      <div class="data-table-pagination">
        <button class="page-btn" data-page="prev" ${this.currentPage === 1 ? 'disabled' : ''}>${this._t('prev_page')}</button>
        ${pages.join('')}
        <button class="page-btn" data-page="next" ${this.currentPage === totalPages ? 'disabled' : ''}>${this._t('next_page')}</button>
      </div>
    `;
  }
  
  /**
   * 绑定事件
   */
  _bindEvents() {
    // 搜索
    const searchInput = this.container.querySelector('.data-table-search');
    if (searchInput) {
      let debounceTimer;
      searchInput.addEventListener('input', (e) => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
          this.search(e.target.value);
        }, 300);
      });
    }
    
    // 搜索字段选择器
    const searchFieldSelect = this.container.querySelector('.search-field-selector');
    if (searchFieldSelect) {
      searchFieldSelect.addEventListener('change', (e) => {
        const value = e.target.value;
        this.setSearchField(value === '__all__' ? null : value);
      });
    }
    
    // 筛选
    this.container.querySelectorAll('.data-table-filter:not(.search-field-selector)').forEach(select => {
      select.addEventListener('change', (e) => {
        const key = e.target.getAttribute('data-filter-key');
        this.setFilter(key, e.target.value);
      });
    });
    
    // 页大小
    const pageSizeSelect = this.container.querySelector('.data-table-pagesize');
    if (pageSizeSelect) {
      pageSizeSelect.addEventListener('change', (e) => {
        this.setPageSize(parseInt(e.target.value, 10));
      });
    }
    
    // 排序
    this.container.querySelectorAll('.data-table-th.sortable').forEach(th => {
      th.addEventListener('click', () => {
        const column = th.getAttribute('data-column');
        this.setSort(column);
      });
    });
    
    // 分页
    this.container.querySelectorAll('.page-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const page = btn.getAttribute('data-page');
        if (page === 'prev') {
          this.goToPage(this.currentPage - 1);
        } else if (page === 'next') {
          this.goToPage(this.currentPage + 1);
        } else {
          this.goToPage(parseInt(page, 10));
        }
      });
    });
    
    // 行点击
    if (this.onRowClick) {
      this.container.querySelectorAll('.data-table-row').forEach(tr => {
        tr.style.cursor = 'pointer';
        tr.addEventListener('click', (e) => {
          // 排除点击 checkbox 的情况
          if (e.target.type === 'checkbox') return;
          const rowId = tr.getAttribute('data-row-id');
          const rowData = this.filteredData.find(r => String(r[this.idKey]) === rowId);
          if (rowData) {
            this.onRowClick(rowData);
          }
        });
      });
    }
    
    // 全选 checkbox
    if (this.selectable) {
      const selectAllCheckbox = this.container.querySelector('.data-table-select-all');
      if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', (e) => {
          if (e.target.checked) {
            this.selectAllOnPage();
          } else {
            this.deselectAllOnPage();
          }
        });
      }
      
      // 行 checkbox
      this.container.querySelectorAll('.data-table-row-checkbox').forEach(checkbox => {
        checkbox.addEventListener('change', (e) => {
          const rowId = checkbox.getAttribute('data-row-id');
          this.toggleRowSelection(rowId);
        });
      });
      
      // 清空选择按钮
      const clearBtn = this.container.querySelector('.batch-clear-btn');
      if (clearBtn) {
        clearBtn.addEventListener('click', () => {
          this.clearSelection();
        });
      }
      
      // 批量操作按钮
      this.container.querySelectorAll('.batch-btn[data-batch-action]').forEach(btn => {
        btn.addEventListener('click', () => {
          const actionIdx = parseInt(btn.getAttribute('data-batch-action'), 10);
          const action = this.batchActions[actionIdx];
          if (action && action.onClick) {
            const selectedRows = this.getSelectedRows();
            action.onClick(selectedRows, this);
          }
        });
      });
    }
  }
  
  /**
   * HTML转义
   */
  _escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
  
  /**
   * 简单翻译（优先使用全局 i18n）
   */
  _t(key) {
    // 尝试使用全局 i18n
    if (typeof i18n !== 'undefined' && i18n.t) {
      const translated = i18n.t('datatable.' + key);
      if (translated && translated !== 'datatable.' + key) {
        return translated;
      }
    }
    
    // 默认翻译
    const defaults = {
      'search_placeholder': '搜索...',
      'per_page': '每页显示：',
      'total': '共',
      'records': '条',
      'all': '全部',
      'prev_page': '上一页',
      'next_page': '下一页',
      'selected': '已选择',
      'items': '项',
      'clear_selection': '清空选择',
      'search_all_fields': '全部字段'
    };
    return defaults[key] || key;
  }
  
  /**
   * 显示加载状态
   */
  showLoading() {
    if (this.container) {
      this.container.innerHTML = `<div class="data-table-loading">${this.loadingMessage}</div>`;
    }
  }
  
  // ============================================================
  // 静态方法：Toast 提示
  // ============================================================
  
  /**
   * 显示 Toast 提示
   * @param {string} message - 消息内容
   * @param {string} type - 类型: 'success', 'error', 'warning', 'info'
   * @param {number} duration - 持续时间（毫秒），默认 3000
   */
  static showToast(message, type = 'success', duration = 3000) {
    // 创建或获取 toast 容器
    let toastContainer = document.querySelector('.data-table-toast-container');
    if (!toastContainer) {
      toastContainer = document.createElement('div');
      toastContainer.className = 'data-table-toast-container';
      document.body.appendChild(toastContainer);
    }
    
    // 创建 toast 元素
    const toast = document.createElement('div');
    toast.className = `data-table-toast toast-${type}`;
    
    // 图标
    const icons = {
      success: '✓',
      error: '✕',
      warning: '⚠',
      info: 'ℹ'
    };
    
    toast.innerHTML = `
      <span class="toast-icon">${icons[type] || icons.info}</span>
      <span class="toast-message">${message}</span>
    `;
    
    // 添加到容器
    toastContainer.appendChild(toast);
    
    // 触发动画
    requestAnimationFrame(() => {
      toast.classList.add('show');
    });
    
    // 自动移除
    setTimeout(() => {
      toast.classList.remove('show');
      toast.classList.add('hide');
      setTimeout(() => {
        toast.remove();
        // 如果容器为空，移除容器
        if (toastContainer && !toastContainer.hasChildNodes()) {
          toastContainer.remove();
        }
      }, 300);
    }, duration);
  }
}

// 导出
if (typeof module !== 'undefined' && module.exports) {
  module.exports = DataTable;
} else {
  window.DataTable = DataTable;
}
