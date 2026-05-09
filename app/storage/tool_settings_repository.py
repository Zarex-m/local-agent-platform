from sqlalchemy import select
from app.storage.database import SessionLocal,ToolSetting
#获取工具的启用状态，默认启用
def get_tool_enabled_setting(tool_name:str)->bool | None:
    db=SessionLocal()
    try:
        setting=db.execute(
            select(ToolSetting).where(ToolSetting.tool_name==tool_name)
        ).scalar_one_or_none()
        if setting is None:
            return None
        return setting.enabled
    finally:
        db.close()
#获取所有工具的启用状态
def get_tool_enabled_settings()->dict[str,bool]:
    db=SessionLocal()
    try:
        settings=db.execute(select(ToolSetting)).scalars().all()
        return {setting.tool_name:setting.enabled for setting in settings}
    finally:
        db.close()

def set_tool_enabled_setting(tool_name:str,enabled:bool)->None:
    db=SessionLocal()
    try:
        setting=db.execute(
            select(ToolSetting).where(ToolSetting.tool_name==tool_name)
        ).scalar_one_or_none()
        if setting is None:
            setting=ToolSetting(tool_name=tool_name,enabled=enabled)
            db.add(setting)
        else:
            setting.enabled=enabled
        db.commit()
        return enabled
    finally:
        db.close()
