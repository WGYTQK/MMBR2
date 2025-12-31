// 在 checkForForms 函数中添加防重复逻辑
async function checkForForms() {
    try {
        const response = await fetch('/api/forms');
        const data = await response.json();
        
        if (data.status === "success") {
            updateFormCount(data.count);
            
            // 防重复：检查是否已经有相同的表单在显示
            data.forms.forEach(form => {
                if (!activeForms.has(form.form_id)) {
                    // 额外检查：是否有相同问题的表单已经在处理中
                    let isDuplicate = false;
                    activeForms.forEach(existingForm => {
                        if (existingForm.question === form.question && 
                            existingForm.type === form.type) {
                            console.log('? 跳过重复表单:', form.question);
                            isDuplicate = true;
                        }
                    });
                    
                    if (!isDuplicate) {
                        displayForm(form);
                        activeForms.set(form.form_id, {
                            ...form,
                            selected_text: '',
                            form_data: {}
                        });
                    }
                }
            });
            
            // ... 清理已不存在的表单 ...
        }
    } catch (error) {
        console.error('获取表单失败:', error);
    }
}

// 或者更简单：修改轮询间隔，避免过于频繁
// 修改初始化部分的轮询间隔
formsCheckInterval = setInterval(checkForForms, 3000); // 从1秒改为3秒
