/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * File Name          : freertos.c
  * Description        : Code for freertos applications
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2025 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */

/* Includes ------------------------------------------------------------------*/
#include "FreeRTOS.h"
#include "task.h"
#include "main.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */

/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
/* USER CODE BEGIN Variables */

/* USER CODE END Variables */

/* Private function prototypes -----------------------------------------------*/
/* USER CODE BEGIN FunctionPrototypes */

/* USER CODE END FunctionPrototypes */

/* Private application code --------------------------------------------------*/
/* USER CODE BEGIN Application */

// The Cortex-M idle task busy-spins by default, so the core ran at 100% duty
// forever -- nothing in this firmware ever executed WFI. Sleeping here drops
// the core clock between interrupts; everything that matters (USB, the SPI DMA
// completion, I2C, the tick) is interrupt-driven and wakes it again.
//
// Not tickless idle: the HAL timebase lives on a TIM (stm32h7xx_hal_timebase_tim.c),
// not SysTick, so it would keep firing at 1 kHz regardless and suppressing the
// FreeRTOS tick would buy almost nothing for considerably more risk.
void vApplicationIdleHook(void)
{
  __WFI();
}

/* USER CODE END Application */

