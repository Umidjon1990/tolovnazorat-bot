import WebApp from '@twa-dev/sdk'

export const tg = WebApp

export const initTelegram = () => {
  tg.ready()
  tg.expand()
  tg.enableClosingConfirmation()
}

export const getUserData = () => {
  const initDataUnsafe = tg.initDataUnsafe
  return {
    user_id: initDataUnsafe?.user?.id,
    username: initDataUnsafe?.user?.username,
    first_name: initDataUnsafe?.user?.first_name,
    last_name: initDataUnsafe?.user?.last_name,
    language_code: initDataUnsafe?.user?.language_code
  }
}

export const getInitData = () => {
  return tg.initData
}

export const showAlert = (message) => {
  tg.showAlert(message)
}

export const showConfirm = (message) => {
  return new Promise((resolve) => {
    tg.showConfirm(message, resolve)
  })
}

export const closeMiniApp = () => {
  tg.close()
}

export const setMainButton = (text, onClick) => {
  tg.MainButton.text = text
  tg.MainButton.onClick(onClick)
  tg.MainButton.show()
}

export const hideMainButton = () => {
  tg.MainButton.hide()
}

export const showBackButton = (onClick) => {
  tg.BackButton.onClick(onClick)
  tg.BackButton.show()
}

export const hideBackButton = () => {
  tg.BackButton.hide()
}
