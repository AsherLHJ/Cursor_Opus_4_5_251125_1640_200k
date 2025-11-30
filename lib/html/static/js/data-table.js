/**
 * DataTable - 可复用的数据表格组件
 * 
 * 功能：
 * - 分页（20/50/100）
 * - 排序（点击表头）
 * - 搜索（文本框）
 * - 筛选（下拉菜单）
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
    
    // 状态
    this.data = [];
    this.filteredData = [];
    this.pageSize = this.defaultPageSize;
    this.currentPage = 1;
    this.sortColumn = null;
    this.sortDirection = 'asc';
    this.filters = {};
    this.searchKeyword = '';
    
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
  }
  
  /**
   * 应用筛选和排序
   */
  _applyFiltersAndSort() {
    let result = [...this.data];
    
    // 应用搜索
    if (this.searchKeyword) {
      const keyword = this.searchKeyword.toLowerCase();
      const searchableCols = this.columns.filter(c => c.searchable).map(c => c.key);
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
   * 渲染表格
   */
  render() {
    if (!this.container) return;
    
    const pageData = this._getPageData();
    const totalPages = this._getTotalPages();
    const totalRecords = this.filteredData.length;
    
    // 构建HTML
    let html = `
      <div class="data-table-wrapper">
        <!-- 工具栏 -->
        <div class="data-table-toolbar">
          <div class="toolbar-left">
            <!-- 搜索框 -->
            <input type="text" class="data-table-search" placeholder="搜索..." value="${this._escapeHtml(this.searchKeyword)}">
            
            <!-- 筛选下拉 -->
            ${this._renderFilters()}
          </div>
          <div class="toolbar-right">
            <!-- 页大小选择 -->
            <label>每页显示：
              <select class="data-table-pagesize">
                ${this.pageSizes.map(size => `<option value="${size}" ${size === this.pageSize ? 'selected' : ''}>${size}</option>`).join('')}
              </select>
            </label>
            <span class="data-table-info">共 ${totalRecords} 条</span>
          </div>
        </div>
        
        <!-- 表格 -->
        <table class="data-table">
          <thead>
            <tr>
              ${this.columns.map(col => this._renderHeaderCell(col)).join('')}
            </tr>
          </thead>
          <tbody>
            ${pageData.length > 0 ? pageData.map(row => this._renderRow(row)).join('') : `<tr><td colspan="${this.columns.length}" class="data-table-empty">${this.emptyMessage}</td></tr>`}
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
    const cells = this.columns.map(col => {
      let content;
      if (col.render && typeof col.render === 'function') {
        content = col.render(row);
      } else {
        content = row[col.key] != null ? this._escapeHtml(String(row[col.key])) : '';
      }
      return `<td>${content}</td>`;
    }).join('');
    
    return `<tr class="data-table-row" data-row-id="${this._escapeHtml(String(row.id || ''))}">${cells}</tr>`;
  }
  
  /**
   * 渲染筛选下拉
   */
  _renderFilters() {
    const filterableCols = this.columns.filter(c => c.filterable && c.filterOptions);
    if (filterableCols.length === 0) return '';
    
    return filterableCols.map(col => {
      const currentValue = this.filters[col.key] || '__all__';
      return `
        <select class="data-table-filter" data-filter-key="${col.key}">
          <option value="__all__">${col.filterLabel || col.label} (全部)</option>
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
        <button class="page-btn" data-page="prev" ${this.currentPage === 1 ? 'disabled' : ''}>上一页</button>
        ${pages.join('')}
        <button class="page-btn" data-page="next" ${this.currentPage === totalPages ? 'disabled' : ''}>下一页</button>
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
    
    // 筛选
    this.container.querySelectorAll('.data-table-filter').forEach(select => {
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
        tr.addEventListener('click', () => {
          const rowId = tr.getAttribute('data-row-id');
          const rowData = this.filteredData.find(r => String(r.id) === rowId);
          if (rowData) {
            this.onRowClick(rowData);
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
   * 显示加载状态
   */
  showLoading() {
    if (this.container) {
      this.container.innerHTML = `<div class="data-table-loading">${this.loadingMessage}</div>`;
    }
  }
}

// 导出
if (typeof module !== 'undefined' && module.exports) {
  module.exports = DataTable;
} else {
  window.DataTable = DataTable;
}

