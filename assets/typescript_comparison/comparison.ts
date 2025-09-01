import ts from "typescript";
import fs from "fs";

function getExportedSymbols(symbol: ts.Symbol): ts.Symbol[] {
  return symbol.exports ? Array.from(symbol.exports.values()) : [];
}

function areContainersAssignable(
  checker: ts.TypeChecker,
  moduleA: ts.Symbol,
  moduleB: ts.Symbol
): any {
  const exportsA = getExportedSymbols(moduleA);
  const exportsB = getExportedSymbols(moduleB);
  const matches: Record<string, string[]> = {};
  let allMatched = true;

  for (const symbolB of exportsB) {
    const typeB = symbolB.valueDeclaration ? checker.getTypeOfSymbolAtLocation(symbolB, symbolB.valueDeclaration) : checker.getDeclaredTypeOfSymbol(symbolB);
    const assignable = [];
    let isAssignable = false;
    for (const symbolA of exportsA) {
      const typeA = symbolA.valueDeclaration ? checker.getTypeOfSymbolAtLocation(symbolA, symbolA.valueDeclaration) : checker.getDeclaredTypeOfSymbol(symbolA);
      if (checker.isTypeAssignableTo(typeA, typeB)) {
        // console.log("Found match:", symbolB.getName(), symbolA.getName());
        assignable.push(symbolA.getName());
        isAssignable = true;
      }
    }
    if (!isAssignable) {
      // console.log("Found no match:", symbolB.getName());
      allMatched = false;
    }
    matches[symbolB.getName()] = assignable;
  }
  return {matched: `${Object.values(matches).filter(value => value.length > 0).length}/${exportsB.length}`, matches: matches};
}

function main() {
    const filePathA = "./generated.d.ts";
    const filePathB = "./manual.d.ts";
    const program = ts.createProgram([filePathA, filePathB], {});
    const checker = program.getTypeChecker();
    const sourceFileA = program.getSourceFile(filePathA);
    const sourceFileB = program.getSourceFile(filePathB);
    if (!sourceFileA || !sourceFileB) throw Error("Source files not found");
    const symbolA = checker.getSymbolAtLocation(sourceFileA);
    const symbolB = checker.getSymbolAtLocation(sourceFileB);
    if (!symbolA || !symbolB) throw Error("Symbol not found");
    
    const resultA = areContainersAssignable(checker, symbolA, symbolB);
    // console.log(`Is generated assignable to manual? ${resultA.all_matched}`);
    const resultB = areContainersAssignable(checker, symbolB, symbolA);
    // console.log(`Is manual assignable to generated? ${resultB.all_matched}`);

    fs.writeFileSync("comparison.json", JSON.stringify({"generated_sub_manual": resultA, "manual_sub_generated": resultB}, null, 2));
}

main();