use keyring::Entry;

/// 系统凭据库服务名（登录态持久化使用）。
const SERVICE: &str = "com.xueban.desktop";

/// 保存凭据到系统 keyring（Windows 凭据管理器 / macOS 钥匙串 / Linux Secret Service）。
#[tauri::command]
fn credential_save(account: String, secret: String) -> Result<(), String> {
    let entry = Entry::new(SERVICE, &account).map_err(|error| error.to_string())?;
    entry.set_password(&secret).map_err(|error| error.to_string())
}

/// 读取凭据；不存在时返回 None（前端回退本地存储）。
#[tauri::command]
fn credential_load(account: String) -> Result<Option<String>, String> {
    let entry = Entry::new(SERVICE, &account).map_err(|error| error.to_string())?;
    match entry.get_password() {
        Ok(secret) => Ok(Some(secret)),
        Err(keyring::Error::NoEntry) => Ok(None),
        Err(error) => Err(error.to_string()),
    }
}

/// 删除凭据（注销时调用）；不存在视为成功。
#[tauri::command]
fn credential_delete(account: String) -> Result<(), String> {
    let entry = Entry::new(SERVICE, &account).map_err(|error| error.to_string())?;
    match entry.delete_credential() {
        Ok(()) | Err(keyring::Error::NoEntry) => Ok(()),
        Err(error) => Err(error.to_string()),
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            credential_save,
            credential_load,
            credential_delete
        ])
        .run(tauri::generate_context!())
        .expect("启动学伴桌面端失败");
}
