// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "Kismet/BlueprintFunctionLibrary.h"
#include "EditorExtraPythonLib.generated.h"

UCLASS()
class UEditorExtraPythonLib : public UBlueprintFunctionLibrary
{
	GENERATED_UCLASS_BODY()

	UFUNCTION(BlueprintCallable, meta = (DisplayName = "Execute Sample function", Keywords = "PythonLib sample test testing"), Category = "PythonLibTesting")
	static float PythonLibSampleFunction(float Param);
};
