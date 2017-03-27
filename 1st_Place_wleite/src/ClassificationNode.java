
public class ClassificationNode {
    ClassificationNode left, right;
    float splitVal;
    int classif, level, splitFeature, startRow, endRow, numRows;
    double impurity;

    public ClassificationNode(int classif, int numRows, double impurtity, int level, int startRow, int endRow) {
        this.classif = classif;
        this.numRows = numRows;
        this.startRow = startRow;
        this.endRow = endRow;
        this.level = level;
        this.impurity = impurtity;
    }

    public float getValue() {
        return classif / (float) numRows;
    }

    public boolean isLeaf() {
        return left == null && right == null;
    }

    public boolean isPure() {
        return classif == 0 || classif == numRows;
    }
}