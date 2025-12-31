# 修改 GlobalFormManager 类中的 add_form 方法
def add_form(self, form_data):
    """添加表单到全局列表 - 防重复版本"""
    with self.lock:
        # 检查是否已存在相同内容的表单（避免重复）
        existing_form_ids = []
        for existing_form in self.pending_forms:
            # 检查是否有相同问题的表单（最近5分钟内）
            if (existing_form.get('question') == form_data.get('question') and
                existing_form.get('type') == form_data.get('type')):
                existing_form_ids.append(existing_form.get('form_id'))
        
        # 如果已有相同表单，不重复添加
        if existing_form_ids:
            print(f"??  表单已存在，不重复添加: {form_data.get('question')}")
            return existing_form_ids[0]  # 返回已有的表单ID
        
        # 清理过期的表单（超过10分钟）
        self._cleanup_old_forms(max_age_minutes=10)
        
        # 生成表单ID（使用更稳定的ID生成方式）
        import hashlib
        content_hash = hashlib.md5(
            f"{form_data.get('question')}_{form_data.get('type')}".encode()
        ).hexdigest()[:8]
        form_id = f"form_{content_hash}_{int(time.time())}"
        
        # 完善表单数据
        form_data['form_id'] = form_id
        form_data['created_at'] = datetime.now().isoformat()
        
        # 添加到列表
        self.pending_forms.append(form_data)
        
        print(f"? 添加全局表单: {form_id}")
        print(f"   问题: {form_data.get('question', '')}")
        print(f"   当前表单数: {len(self.pending_forms)}")
        
        return form_id

# 或者更简单的：修改 /external/options 路由，避免重复调用
@app.route('/external/options', methods=['GET'])
def receive_external_options():
    """接收外部选项请求 - 添加防重复检查"""
    # 从查询参数获取数据
    request_type = request.args.get('type', '1')
    question = request.args.get('question', '')
    
    # 检查是否已有相同问题的表单
    existing_forms = form_manager.get_all_forms()
    for form in existing_forms:
        if (form.get('question') == question and 
            form.get('type') == request_type):
            print(f"??  表单已存在，跳过: {question}")
            return jsonify({
                "status": "success",
                "message": "表单已存在",
                "form_id": form.get('form_id'),
                "existing": True
            })
    
    # ... 原有的处理逻辑 ...
